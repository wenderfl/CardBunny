import os
import subprocess
import json
import shutil
import threading
import uuid
import pysrt
from concurrent.futures import ThreadPoolExecutor, as_completed
from auto_anki.config import CONFIG
from auto_anki.anki_client import invoke_anki
from auto_anki.mapper import map_fields

# Detectar número de CPUs disponíveis para ajustar paralelismo automaticamente
_CPU_COUNT = os.cpu_count() or 4

def _get_worker_count():
    """
    Calcula o número ideal de workers baseado nos CPUs disponíveis.
    Cada worker roda 1 processo ffmpeg. ffmpeg internamente usa threads adicionais.
    Limitamos a metade dos CPUs para não saturar completamente o sistema.
    """
    # Cada processo lê o vídeo e também cria threads internas. Um quarto dos
    # CPUs evita contenção de disco/memória sem serializar máquinas menores.
    return max(1, min(8, _CPU_COUNT // 4))

def _probe_media(video_path):
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if not ffmpeg_path or not ffprobe_path:
        raise RuntimeError("FFmpeg e FFprobe precisam estar disponíveis no PATH.")
    try:
        result = subprocess.run(
            [ffprobe_path, "-v", "error", "-show_streams", "-show_format", "-of", "json", video_path],
            capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFprobe não conseguiu analisar o vídeo: {result.stderr.strip()[-500:]}")
        metadata = json.loads(result.stdout)
        streams = metadata.get("streams", [])
        if not any(stream.get("codec_type") == "video" for stream in streams):
            raise RuntimeError("O arquivo selecionado não possui faixa de vídeo.")
        if not any(stream.get("codec_type") == "audio" for stream in streams):
            raise RuntimeError("O arquivo selecionado não possui faixa de áudio.")
        duration = float(metadata.get("format", {}).get("duration", 0))
        if duration <= 0:
            raise RuntimeError("Não foi possível determinar a duração do vídeo.")
        return ffmpeg_path, duration
    except (ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Metadados inválidos retornados pelo FFprobe: {error}") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("FFprobe excedeu o tempo limite ao analisar o vídeo.") from error

def _validate_subtitles(subs_en, subs_pt, video_duration):
    if not subs_en:
        raise RuntimeError("A transcrição original não contém nenhuma fala.")
    if len(subs_en) != len(subs_pt):
        raise RuntimeError(
            f"As legendas estão desalinhadas: {len(subs_en)} trechos originais e "
            f"{len(subs_pt)} traduções."
        )
    duration_ms = round(video_duration * 1000)
    for index, (sub_en, sub_pt) in enumerate(zip(subs_en, subs_pt), start=1):
        start_ms, end_ms = sub_en.start.ordinal, sub_en.end.ordinal
        if not sub_en.text.strip() or not sub_pt.text.strip():
            raise RuntimeError(f"O trecho {index} possui texto original ou tradução vazia.")
        if start_ms < 0 or end_ms <= start_ms:
            raise RuntimeError(f"O trecho {index} possui timestamps inválidos.")
        if start_ms >= duration_ms or end_ms > duration_ms + 500:
            raise RuntimeError(
                f"O trecho {index} termina fora do vídeo "
                f"({end_ms / 1000:.3f}s > {video_duration:.3f}s)."
            )
        if (abs(sub_pt.start.ordinal - start_ms) > 500 or
                abs(sub_pt.end.ordinal - end_ms) > 500):
            raise RuntimeError(f"O trecho traduzido {index} não corresponde ao intervalo original.")

def slice_and_export_to_anki(video_path, srt_en, srt_pt, deck_name, work_dir, field_mapping=None):
    print(f"Iniciando fatiamento e exportação para o Anki...")
    print(f"Paralelismo configurado: {_get_worker_count()} workers em {_CPU_COUNT} núcleos disponíveis.")
    
    ffmpeg_path, video_duration = _probe_media(video_path)
    
    # Mapear campos do modelo automaticamente
    dynamic_fields = field_mapping or map_fields(CONFIG['anki']['model_name'])
    if not dynamic_fields:
        raise RuntimeError("Falha ao mapear os campos do modelo do Anki.")
    
    subs_en = pysrt.open(srt_en, encoding='utf-8')
    subs_pt = pysrt.open(srt_pt, encoding='utf-8')

    _validate_subtitles(subs_en, subs_pt, video_duration)

    if invoke_anki('createDeck', deck=deck_name) is None:
        raise RuntimeError("Não foi possível criar ou acessar o deck no Anki.")
    
    output_dir = os.path.join(work_dir, "slices")
    os.makedirs(output_dir, exist_ok=True)
    
    base_name = "vid_" + uuid.uuid4().hex[:12]
    creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    
    # Número de threads que cada ffmpeg pode usar internamente
    # Com muitos workers, usamos poucas threads por ffmpeg para não saturar
    ffmpeg_threads = max(1, min(4, _CPU_COUNT // _get_worker_count()))
    
    def process_media(args):
        """
        Processa um único clipe usando UMA ÚNICA chamada ffmpeg com múltiplos outputs.
        
        Otimizações:
        - 1 chamada ffmpeg → webm + mp3 + jpg (em vez de 3 chamadas separadas)
        - Snapshot extraído diretamente do vídeo original (não do webm)
        - Seek rápido: -ss antes de -i (stream copy até o ponto)
        - Threads por processo configuradas dinamicamente
        """
        i, sub_en, sub_pt = args
        start_sec = sub_en.start.ordinal / 1000.0
        end_sec = min(sub_en.end.ordinal / 1000.0, video_duration)
        delta_sec = end_sec - start_sec
        
        if delta_sec <= 0:
            return None
        
        out_vid   = os.path.join(output_dir, f"{base_name}_{i}.webm")
        out_audio = os.path.join(output_dir, f"{base_name}_{i}.mp3")
        out_img   = os.path.join(output_dir, f"{base_name}_{i}.jpg")
        
        # ─── UMA ÚNICA CHAMADA FFMPEG com 3 outputs ───────────────────────────
        # -ss antes de -i: seek rápido (decodifica apenas a partir do keyframe próximo)
        # -t limita a duração
        # Output 1: WebM com libvpx (vídeo) + libvorbis (áudio)
        # Output 2: MP3 com libmp3lame
        # Output 3: JPEG do frame central, diretamente do vídeo original
        cmd = [
            ffmpeg_path, "-y",
            "-threads", str(ffmpeg_threads),    # threads globais para o processo
            "-ss", str(start_sec),              # seek rápido ANTES do input
            "-i", video_path,
            "-t", str(delta_sec),
            
            # --- Output 1: WebM (vídeo + áudio vorbis) ---
            "-map", "0:v:0",
            "-map", "0:a:0",
            "-c:v", "libvpx",
            "-auto-alt-ref", "0",
            "-quality", "realtime",             # modo rápido (vs good/best)
            "-cpu-used", "8",                   # máxima velocidade (0-16 para libvpx)
            "-b:v", "0",                        # controle por qualidade, não bitrate fixo
            "-crf", "33",                       # qualidade aceitável (10=máxima, 63=mínima)
            "-c:a", "libvorbis",
            "-b:a", "96k",
            "-vf", "scale=-2:360",              # 360p é suficiente para estudo — 4x mais rápido
            out_vid,
            
            # --- Output 2: MP3 (áudio) ---
            "-t", str(delta_sec),              # cada output precisa do seu próprio limite
            "-map", "0:a:0",
            "-c:a", "libmp3lame",
            "-q:a", "4",                        # qualidade VBR (0=melhor, 9=pior), 4≈128kbps
            out_audio,
            
            # --- Output 3: JPEG (snapshot do meio do clipe) ---
            "-ss", str(delta_sec / 2.0),
            "-map", "0:v:0",
            "-vf", "scale=-2:360",
            "-vframes", "1",
            "-q:v", "5",                        # qualidade JPEG (2=alta, 10=baixa)
            out_img,
        ]
        
        for attempt in range(1, 3):
            try:
                completed = subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    creationflags=creation_flags,
                    timeout=max(60, min(300, delta_sec * 20)),
                )
                outputs_ok = all(
                    os.path.isfile(path) and os.path.getsize(path) > 0
                    for path in (out_vid, out_audio, out_img)
                )
                if completed.returncode == 0 and outputs_ok:
                    return i, sub_en, sub_pt, out_vid, out_audio, out_img
                print(
                    f"\nFFmpeg falhou no clipe {i} "
                    f"(tentativa {attempt}/2, código {completed.returncode}): "
                    f"{completed.stderr.decode(errors='replace').strip()[-300:]}"
                )
            except subprocess.TimeoutExpired:
                print(f"\nTimeout no clipe {i} (tentativa {attempt}/2).")
            except Exception as e:
                print(f"\nErro no clipe {i} (tentativa {attempt}/2): {e}")
        return None

    # ── FASE 1: Geração de mídia em paralelo ─────────────────────────────────
    tasks = [(i, sub_en, sub_pt) for i, (sub_en, sub_pt) in enumerate(zip(subs_en, subs_pt))]
    total = len(tasks)
    valid_cards = [None] * total  # pré-aloca para manter ordem
    generated = 0
    lock = threading.Lock()
    
    print(f"Gerando {total} clipes em paralelo ({_get_worker_count()} workers)...")
    
    with ThreadPoolExecutor(max_workers=_get_worker_count()) as executor:
        future_to_idx = {executor.submit(process_media, task): task[0] for task in tasks}
        for future in as_completed(future_to_idx):
            result = future.result()
            if result:
                valid_cards[result[0]] = result
                with lock:
                    generated += 1
                print(f"Clipes gerados: {generated}/{total}", end="\r")
    
    # Filtrar nulos e preservar ordem da legenda
    valid_cards = [c for c in valid_cards if c is not None]
    print(f"\n{len(valid_cards)}/{total} clipes gerados com sucesso.")
    if len(valid_cards) != total:
        missing = total - len(valid_cards)
        raise RuntimeError(
            f"{missing} clipe(s) não puderam ser gerados. A exportação foi interrompida "
            "para não criar um deck com transcrições ausentes."
        )
    
    # ── FASE 2: Upload para o Anki em paralelo ───────────────────────────────
    print(f"Enviando {len(valid_cards)} cards para o Anki (paralelizado)...")
    
    def upload_card(card_data):
        """Upload de mídia + criação de nota para um card."""
        i, sub_en, sub_pt, out_vid, out_audio, out_img = card_data
        vid_filename   = os.path.basename(out_vid)
        audio_filename = os.path.basename(out_audio)
        img_filename   = os.path.basename(out_img)
        
        # Upload dos 3 arquivos de mídia
        stored_media = (
            invoke_anki('storeMediaFile', filename=vid_filename, path=os.path.abspath(out_vid)),
            invoke_anki('storeMediaFile', filename=audio_filename, path=os.path.abspath(out_audio)),
            invoke_anki('storeMediaFile', filename=img_filename, path=os.path.abspath(out_img)),
        )
        if any(result is None for result in stored_media):
            return i, None, "falha ao enviar uma ou mais mídias"
        
        fields = {}
        # Audio: [sound:vid_...mp3] — arquivo de áudio MP3 com tag [sound:]
        if dynamic_fields.get('audio'):
            fields[dynamic_fields['audio']] = f"[sound:{audio_filename}]"
        # Clip: vid_...webm — apenas o nome do arquivo de vídeo WEBM (sem tag [sound:])
        if dynamic_fields.get('clip'):
            fields[dynamic_fields['clip']] = vid_filename
        # Snapshot: <img src="vid_...jpg"> — imagem do frame da cena
        if dynamic_fields.get('snapshot'):
            fields[dynamic_fields['snapshot']] = f'<img src="{img_filename}">'
        # Legenda em inglês (texto original)
        if dynamic_fields.get('english_subtitle'):
            fields[dynamic_fields['english_subtitle']] = sub_en.text
        # Legenda em português (tradução)
        if dynamic_fields.get('portuguese_subtitle'):
            fields[dynamic_fields['portuguese_subtitle']] = sub_pt.text
        # Index: [sound:vid_...webm] — arquivo de vídeo WEBM com tag [sound:]
        if dynamic_fields.get('index'):
            fields[dynamic_fields['index']] = f"[sound:{vid_filename}]"
        
        note = {
            "deckName": deck_name,
            "modelName": CONFIG['anki']['model_name'],
            "fields": fields,
            "options": {"allowDuplicate": True, "duplicateScope": "deck"},
            "tags": ["auto-anki"]
        }
        
        note_id = invoke_anki('addNote', note=note)
        if note_id is None:
            return i, None, "falha ao criar a nota"
        return i, note_id, None
    
    # Upload paralelo com até 4 workers (AnkiConnect não lida bem com muitos simultâneos)
    uploaded = 0
    failed = 0
    uploaded_note_ids = []
    anki_workers = min(4, len(valid_cards))
    
    with ThreadPoolExecutor(max_workers=anki_workers) as executor:
        future_to_card = {executor.submit(upload_card, card): card[0] for card in valid_cards}
        for future in as_completed(future_to_card):
            idx = future_to_card[future]
            try:
                idx, note_id, error = future.result()
            except Exception as exception:
                note_id, error = None, str(exception)
            if note_id is not None:
                uploaded += 1
                uploaded_note_ids.append(note_id)
            else:
                failed += 1
                print(f"\nFalha ao adicionar card {idx}: {error}.")
            print(f"Cards enviados: {uploaded}/{len(valid_cards)}", end="\r")

    if failed:
        print("\nFalha no envio. Revertendo notas e mídias desta execução...")
        if uploaded_note_ids:
            invoke_anki('deleteNotes', notes=uploaded_note_ids)
        media_names = {
            os.path.basename(path)
            for card in valid_cards
            for path in card[3:6]
        }
        for filename in media_names:
            invoke_anki('deleteMediaFile', filename=filename)
        raise RuntimeError(
            f"{failed} card(s) falharam no envio. As notas desta execução foram revertidas."
        )

    print(f"\nConcluído: {uploaded} cards adicionados ao Anki, {failed} falhas.")
