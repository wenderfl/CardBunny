import math
import os
import time

import pysrt
try:
    import hf_xet  # Incluído explicitamente na build para acelerar downloads do Hugging Face.
except ImportError:
    hf_xet = None
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio
from faster_whisper.utils import download_model
from faster_whisper.vad import VadOptions, get_speech_timestamps

from auto_anki.config import CONFIG


def _clock(seconds):
    seconds = max(0, round(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _normalize_segments(raw_segments, total_duration=None, show_progress=False, stats=None):
    """Materializa e valida todos os segmentos antes de criar qualquer SRT."""
    normalized = []
    previous_start_ms = -1
    started_at = time.monotonic()
    last_reported_percent = 0

    if show_progress and total_duration:
        print(
            f"PROGRESSO_TRANSCRICAO: 0% | áudio 00:00:00/{_clock(total_duration)} "
            "| 0 trechos | calculando tempo restante"
        )

    if stats is None:
        stats = {}
    stats.setdefault("clamped_to_duration", 0)
    stats.setdefault("outside_audio", 0)

    for position, segment in enumerate(raw_segments, start=1):
        text = " ".join(str(getattr(segment, "text", "")).split())
        if not text:
            raise RuntimeError(
                f"O Whisper retornou o segmento {position} sem texto. "
                "A transcrição foi interrompida para não ignorá-lo silenciosamente."
            )

        start = float(getattr(segment, "start", -1))
        end = float(getattr(segment, "end", -1))
        if not math.isfinite(start) or not math.isfinite(end):
            raise RuntimeError(f"O Whisper gerou timestamps inválidos no segmento {position}.")

        if total_duration and start >= total_duration:
            stats["outside_audio"] += 1
            print(
                f"Aviso: segmento {position} começava após o fim do áudio "
                f"({_clock(start)} > {_clock(total_duration)}) e foi classificado "
                "como hallucinação fora da mídia."
            )
            continue
        if total_duration and end > total_duration:
            stats["clamped_to_duration"] += 1
            print(
                f"Aviso: término do segmento {position} ajustado de "
                f"{_clock(end)} para {_clock(total_duration)}."
            )
            end = total_duration

        start_ms = max(0, round(start * 1000))
        end_ms = round(end * 1000)
        if end_ms <= start_ms:
            raise RuntimeError(
                f"O Whisper gerou um intervalo vazio/invertido no segmento {position}: "
                f"{start:.3f}s até {end:.3f}s."
            )
        if start_ms < previous_start_ms:
            raise RuntimeError(
                f"O Whisper gerou segmentos fora de ordem na posição {position}."
            )

        normalized.append((start_ms, end_ms, text))
        previous_start_ms = start_ms

        if show_progress and total_duration:
            percent = min(100, int((end / total_duration) * 100))
            if percent >= last_reported_percent + 5 or percent == 100:
                elapsed = max(0.001, time.monotonic() - started_at)
                progress_end = min(end, total_duration)
                audio_rate = progress_end / elapsed
                eta = (total_duration - progress_end) / audio_rate if audio_rate > 0 else 0
                print(
                    f"PROGRESSO_TRANSCRICAO: {percent}% | "
                    f"áudio {_clock(progress_end)}/{_clock(total_duration)} | "
                    f"{len(normalized)} trechos | restante ~{_clock(eta)}"
                )
                last_reported_percent = percent

    if not normalized:
        raise RuntimeError("O Whisper não encontrou nenhuma fala válida no vídeo.")
    return normalized


def _uncovered_from_regions(speech_regions, segments):
    uncovered = []
    for region in speech_regions:
        start_ms = round(region["start"] / 16)
        end_ms = round(region["end"] / 16)
        duration_ms = end_ms - start_ms
        if duration_ms < 500:
            continue
        overlap_ms = sum(
            max(0, min(end_ms, segment_end) - max(start_ms, segment_start))
            for segment_start, segment_end, _ in segments
        )
        required_overlap = min(300, round(duration_ms * 0.2))
        if overlap_ms < required_overlap:
            uncovered.append((start_ms, end_ms))
    return uncovered


def _find_uncovered_speech(video_path, segments):
    """Retorna regiões detectadas como voz que não possuem texto sobreposto."""
    try:
        audio = decode_audio(video_path, sampling_rate=16000)
        speech_regions = get_speech_timestamps(
            audio,
            VadOptions(
                threshold=0.65,
                min_speech_duration_ms=500,
                min_silence_duration_ms=500,
                speech_pad_ms=150,
            ),
            sampling_rate=16000,
        )
    except Exception as error:
        raise RuntimeError(f"Falha ao auditar regiões de fala do áudio: {error}") from error

    return speech_regions, _uncovered_from_regions(speech_regions, segments)


def _recover_uncovered_speech(model, video_path, segments, uncovered):
    if not uncovered:
        return segments, 0

    print(f"Auditoria encontrou {len(uncovered)} região(ões) de voz sem texto. Recuperando...")
    clip_timestamps = [value / 1000 for interval in uncovered for value in interval]
    try:
        retry_segments, _ = model.transcribe(
            video_path,
            beam_size=5,
            language="en",
            task="transcribe",
            temperature=0.0,
            vad_filter=False,
            no_speech_threshold=1.0,
            condition_on_previous_text=False,
            clip_timestamps=clip_timestamps,
        )
        recovered = _normalize_segments(retry_segments)
    except Exception as error:
        raise RuntimeError(f"Falha ao recuperar regiões de voz sem transcrição: {error}") from error

    merged = list(segments)
    added = 0
    for candidate in recovered:
        start_ms, end_ms, text = candidate
        duration_ms = end_ms - start_ms
        largest_overlap = max(
            (max(0, min(end_ms, old_end) - max(start_ms, old_start))
             for old_start, old_end, _ in merged),
            default=0,
        )
        if largest_overlap < duration_ms * 0.5:
            merged.append(candidate)
            added += 1
    merged.sort(key=lambda item: (item[0], item[1]))
    return merged, added


def _write_and_validate_srt(segments, srt_path):
    """Grava atomicamente e confirma que nenhuma entrada foi perdida no arquivo."""
    temporary_path = f"{srt_path}.tmp"
    try:
        with open(temporary_path, "w", encoding="utf-8", newline="\n") as file:
            for index, (start_ms, end_ms, text) in enumerate(segments, start=1):
                file.write(
                    f"{index}\n{format_timestamp_ms(start_ms)} --> "
                    f"{format_timestamp_ms(end_ms)}\n{text}\n\n"
                )

        parsed = pysrt.open(temporary_path, encoding="utf-8")
        if len(parsed) != len(segments):
            raise RuntimeError(
                f"O SRT salvo contém {len(parsed)} entradas, mas o Whisper gerou "
                f"{len(segments)} segmentos."
            )
        for index, (subtitle, expected) in enumerate(zip(parsed, segments), start=1):
            start_ms, end_ms, text = expected
            if subtitle.start.ordinal != start_ms or subtitle.end.ordinal != end_ms:
                raise RuntimeError(f"Os timestamps mudaram ao salvar o segmento {index}.")
            if " ".join(subtitle.text.split()) != text:
                raise RuntimeError(f"O texto mudou ao salvar o segmento {index}.")

        os.replace(temporary_path, srt_path)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


def transcribe_video(video_path, work_dir):
    print("Iniciando transcrição local com Whisper...")
    print(
        "Carregando cérebro da Inteligência Artificial... "
        "(A primeira execução pode baixar o modelo e demorar alguns minutos)"
    )

    if not video_path or not os.path.isfile(video_path):
        raise FileNotFoundError(f"Arquivo de vídeo não encontrado: {video_path}")

    whisper_config = CONFIG["whisper"]
    model_size = whisper_config["model_size"]
    device = whisper_config["device"]
    compute_type = whisper_config["compute_type"]
    cpu_threads = whisper_config.get("cpu_threads", 4)

    try:
        print(
            f"Preparando modelo Whisper '{model_size}'. Na primeira execução, "
            "o download pode ser grande e demorar alguns minutos..."
        )
        model_path = download_model(model_size)
        print(f"Modelo Whisper '{model_size}' disponível. Iniciando transcrição...")
        model = WhisperModel(
            model_path,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
        )
    except Exception as error:
        raise RuntimeError(
            f"Falha ao baixar ou carregar o modelo Whisper '{model_size}': {error}"
        ) from error

    try:
        raw_segments, info = model.transcribe(
            video_path,
            beam_size=5,
            language="en",
            task="transcribe",
            temperature=0.0,
            vad_filter=False,
            # Falas de filmes/jogos podem ficar abaixo de música e efeitos.
            no_speech_threshold=0.8,
            condition_on_previous_text=True,
            word_timestamps=True,
            hallucination_silence_threshold=2.0,
        )
        # A inferência acontece durante a iteração; materializar aqui garante que
        # erros no meio do áudio não produzam um SRT parcial.
        duration = float(getattr(info, "duration", 0) or 0)
        normalization_stats = {}
        segments = _normalize_segments(
            raw_segments,
            total_duration=duration,
            show_progress=True,
            stats=normalization_stats,
        )

        print("Auditando cobertura de voz da transcrição...")
        speech_regions, uncovered = _find_uncovered_speech(video_path, segments)
        initial_uncovered_count = len(uncovered)
        segments, recovered_count = _recover_uncovered_speech(
            model, video_path, segments, uncovered
        )
        remaining_uncovered = _uncovered_from_regions(speech_regions, segments)
        if remaining_uncovered:
            intervals = ", ".join(
                f"{format_timestamp_ms(start)}–{format_timestamp_ms(end)}"
                for start, end in remaining_uncovered[:8]
            )
            raise RuntimeError(
                f"A auditoria ainda encontrou {len(remaining_uncovered)} região(ões) "
                f"de voz sem transcrição: {intervals}."
            )
    except Exception as error:
        if isinstance(error, RuntimeError):
            raise
        raise RuntimeError(f"Falha durante a transcrição do vídeo: {error}") from error

    print("Idioma da transcrição original: inglês (en)")
    srt_path = os.path.join(work_dir, "original.srt")
    try:
        _write_and_validate_srt(segments, srt_path)
        audit_path = os.path.join(work_dir, "transcription_audit.txt")
        with open(audit_path, "w", encoding="utf-8", newline="\n") as audit:
            audit.write("Auditoria de cobertura da transcrição\n")
            audit.write(f"Regiões de voz detectadas: {len(speech_regions)}\n")
            audit.write(f"Regiões inicialmente sem texto: {initial_uncovered_count}\n")
            audit.write(f"Segmentos recuperados: {recovered_count}\n")
            audit.write(
                f"Términos ajustados à duração da mídia: "
                f"{normalization_stats['clamped_to_duration']}\n"
            )
            audit.write(
                f"Hallucinações totalmente fora da mídia: "
                f"{normalization_stats['outside_audio']}\n"
            )
            audit.write("Regiões de voz restantes sem texto: 0\n")
            audit.write(f"Segmentos finais no SRT: {len(segments)}\n")
    except Exception as error:
        if isinstance(error, RuntimeError):
            raise
        raise RuntimeError(f"Falha ao salvar a legenda original: {error}") from error

    first_start = format_timestamp_ms(segments[0][0])
    last_end = format_timestamp_ms(segments[-1][1])
    print(
        f"Transcrição validada: {len(segments)} trechos "
        f"({first_start} até {last_end})."
    )
    print(f"Transcrição concluída: {srt_path}")
    return srt_path


def format_timestamp_ms(total_milliseconds):
    total_milliseconds = int(total_milliseconds)
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def format_timestamp(seconds):
    """Compatibilidade para chamadas existentes e testes externos."""
    if not math.isfinite(float(seconds)):
        raise ValueError("Timestamp inválido.")
    return format_timestamp_ms(max(0, round(float(seconds) * 1000)))
