import math
import os
import time

import pysrt
try:
    import hf_xet  # Included explicitly in the build to accelerate Hugging Face downloads.
except ImportError:
    hf_xet = None
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio
from faster_whisper.utils import download_model
from faster_whisper.vad import VadOptions, get_speech_timestamps

from cardbunny.config import CONFIG


def _clock(seconds):
    seconds = max(0, round(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _normalize_segments(raw_segments, total_duration=None, show_progress=False, stats=None, allow_empty=False):
    """Materializes and validates all segments before creating any SRT."""
    normalized = []
    previous_start_ms = -1
    started_at = time.monotonic()
    last_reported_percent = 0

    if show_progress and total_duration:
        print(
            f"transcription_progress: 0% | audio 00:00:00/{_clock(total_duration)} "
            "| 0 segments | calculating remaining time"
        )

    if stats is None:
        stats = {}
    stats.setdefault("clamped_to_duration", 0)
    stats.setdefault("outside_audio", 0)

    for position, segment in enumerate(raw_segments, start=1):
        text = " ".join(str(getattr(segment, "text", "")).split())
        if not text:
            raise RuntimeError(
                f"Whisper returned segment {position} without text. "
                "Transcription was interrupted to avoid ignoring it silently."
            )

        start = float(getattr(segment, "start", -1))
        end = float(getattr(segment, "end", -1))
        if not math.isfinite(start) or not math.isfinite(end):
            raise RuntimeError(f"Whisper generated invalid timestamps in segment {position}.")

        if total_duration and start >= total_duration:
            stats["outside_audio"] += 1
            print(
                f"Warning: segment {position} started after the end of the audio "
                f"({_clock(start)} > {_clock(total_duration)}) and was classified "
                "as hallucination outside the media."
            )
            continue
        if total_duration and end > total_duration:
            stats["clamped_to_duration"] += 1
            print(
                f"Warning: end of segment {position} adjusted from "
                f"{_clock(end)} to {_clock(total_duration)}."
            )
            end = total_duration

        start_ms = max(0, round(start * 1000))
        end_ms = round(end * 1000)
        if end_ms <= start_ms:
            print(
                f"Warning: Ignoring empty/inverted interval in segment {position}: "
                f"{start:.3f}s to {end:.3f}s."
            )
            continue
        if start_ms < previous_start_ms:
            print(
                f"Warning: Segment {position} started before previous segment "
                f"({start_ms}ms < {previous_start_ms}ms). Adjusting to preserve order."
            )
            start_ms = previous_start_ms
            if end_ms <= start_ms:
                continue

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
                    f"transcription_progress: {percent}% | "
                    f"audio {_clock(progress_end)}/{_clock(total_duration)} | "
                    f"{len(normalized)} segments | remaining ~{_clock(eta)}"
                )
                last_reported_percent = percent

    if not normalized and not allow_empty:
        raise RuntimeError("Whisper did not find any valid speech in the video.")
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
    """Returns regions detected as voice that do not have overlapping text."""
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
        raise RuntimeError(f"Failed to audit speech regions from audio: {error}") from error

    return speech_regions, _uncovered_from_regions(speech_regions, segments)


def _recover_uncovered_speech(model, video_path, segments, uncovered):
    if not uncovered:
        return segments, 0

    print(f"Audit found {len(uncovered)} voice region(s) without text. Recovering...")
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
        recovered = _normalize_segments(retry_segments, allow_empty=True)
    except Exception as error:
        raise RuntimeError(f"Failed to recover voice regions without transcription: {error}") from error

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
    """Writes atomically and confirms that no entry was lost in the file."""
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
                f"The saved SRT contains {len(parsed)} entries, but Whisper generated "
                f"{len(segments)} segments."
            )
        for index, (subtitle, expected) in enumerate(zip(parsed, segments), start=1):
            start_ms, end_ms, text = expected
            if subtitle.start.ordinal != start_ms or subtitle.end.ordinal != end_ms:
                raise RuntimeError(f"Timestamps changed when saving segment {index}.")
            if " ".join(subtitle.text.split()) != text:
                raise RuntimeError(f"Text changed when saving segment {index}.")

        os.replace(temporary_path, srt_path)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


def transcribe_video(video_path, work_dir):
    print("starting local transcription with whisper...")
    print(
        "Loading Artificial Intelligence brain... "
        "(First execution might download the model and take a few minutes)"
    )

    if not video_path or not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    whisper_config = CONFIG["whisper"]
    model_size = whisper_config["model_size"]
    device = whisper_config["device"]
    compute_type = whisper_config["compute_type"]
    cpu_threads = whisper_config.get("cpu_threads", 4)

    try:
        print(
            f"preparing whisper model '{model_size}'. On first run, "
            "the download can be large and take a few minutes..."
        )
        model_path = download_model(model_size)
        print(f"whisper model '{model_size}' available. Starting transcription...")
        model = WhisperModel(
            model_path,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
        )
    except Exception as error:
        raise RuntimeError(
            f"Failed to download or load whisper model '{model_size}': {error}"
        ) from error

    try:
        whisper_lang = whisper_config.get("language", "en")
        raw_segments, info = model.transcribe(
            video_path,
            beam_size=1,
            language=whisper_lang,
            task="transcribe",
            temperature=0.0,
            vad_filter=True,
            # Speech in movies/games can be under music and effects.
            no_speech_threshold=0.8,
            condition_on_previous_text=True,
            word_timestamps=True,
            hallucination_silence_threshold=2.0,
        )
        # Inference happens during iteration; materializing here ensures errors in the middle of the audio don't produce a partial SRT.
        duration = float(getattr(info, "duration", 0) or 0)
        normalization_stats = {}
        segments = _normalize_segments(
            raw_segments,
            total_duration=duration,
            show_progress=True,
            stats=normalization_stats,
        )

        print("auditing voice coverage...")
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
                f"Audit still found {len(remaining_uncovered)} voice region(s) "
                f"without transcription: {intervals}."
            )
    except Exception as error:
        if isinstance(error, RuntimeError):
            raise
        raise RuntimeError(f"Failed during video transcription: {error}") from error

    print("Original transcription language: english (en)")
    srt_path = os.path.join(work_dir, "original.srt")
    try:
        _write_and_validate_srt(segments, srt_path)
        audit_path = os.path.join(work_dir, "transcription_audit.txt")
        with open(audit_path, "w", encoding="utf-8", newline="\n") as audit:
            audit.write("Transcription coverage audit\n")
            audit.write(f"Detected voice regions: {len(speech_regions)}\n")
            audit.write(f"Regions initially without text: {initial_uncovered_count}\n")
            audit.write(f"Recovered segments: {recovered_count}\n")
            audit.write(
                f"Ends adjusted to media duration: "
                f"{normalization_stats['clamped_to_duration']}\n"
            )
            audit.write(
                f"Hallucinations totally outside media: "
                f"{normalization_stats['outside_audio']}\n"
            )
            audit.write("Remaining voice regions without text: 0\n")
            audit.write(f"Final segments in SRT: {len(segments)}\n")
    except Exception as error:
        if isinstance(error, RuntimeError):
            raise
        raise RuntimeError(f"Failed to save original subtitle: {error}") from error

    first_start = format_timestamp_ms(segments[0][0])
    last_end = format_timestamp_ms(segments[-1][1])
    print(
        f"Validated transcription: {len(segments)} segments "
        f"({first_start} to {last_end})."
    )
    print(f"Transcription completed: {srt_path}")
    return srt_path


def format_timestamp_ms(total_milliseconds):
    total_milliseconds = int(total_milliseconds)
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def format_timestamp(seconds):
    """Compatibility for existing calls and external tests."""
    if not math.isfinite(float(seconds)):
        raise ValueError("Invalid timestamp.")
    return format_timestamp_ms(max(0, round(float(seconds) * 1000)))
