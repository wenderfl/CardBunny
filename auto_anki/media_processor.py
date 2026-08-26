import os
import subprocess
import datetime
import threading
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
    # Usar até metade dos núcleos para workers de ffmpeg (cada ffmpeg usa ~2 threads)
    workers = max(4, _CPU_COUNT // 2)
    # Cap em 16 para não criar contenção excessiva de I/O
    return min(workers, 16)

def slice_and_export_to_anki(video_path, srt_en, srt_pt, deck_name, work_dir, field_mapping=None):
    print(f"Iniciando fatiamento e exportação para o Anki...")
    print(f"Paralelismo configurado: {_get_worker_count()} workers em {_CPU_COUNT} núcleos disponíveis.")
    
    # Criar deck
    invoke_anki('createDeck', deck=deck_name)
    
    # Mapear campos do modelo automaticamente
    dynamic_fields = field_mapping or map_fields(CONFIG['anki']['model_name'])
    if not dynamic_fields:
        print("Erro crítico: Falha ao mapear os campos. Abortando exportação.")
        return
    
    subs_en = pysrt.open(srt_en, encoding='utf-8')
    subs_pt = pysrt.open(srt_pt, encoding='utf-8')
    
    output_dir = os.path.join(work_dir, "slices")
    os.makedirs(output_dir, exist_ok=True)
    
    base_name = "vid_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
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
        delta_sec = (sub_en.end.ordinal - sub_en.start.ordinal) / 1000.0
        
        if delta_sec <= 0:
            return None
        
        mid_sec = start_sec + delta_sec / 2.0
        
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
            "ffmpeg", "-y",
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
            "-map", "0:a:0",
            "-c:a", "libmp3lame",
            "-q:a", "4",                        # qualidade VBR (0=melhor, 9=pior), 4≈128kbps
            out_audio,
            
            # --- Output 3: JPEG (snapshot do meio do clipe) ---
            "-map", "0:v:0",
            "-vf", f"select=eq(n\\,0),scale=-2:360",   # 1º frame disponível após o seek
            "-vframes", "1",
            "-q:v", "5",                        # qualidade JPEG (2=alta, 10=baixa)
            out_img,
        ]
        
        try:
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
                timeout=60  # se travar, abandona após 60s
            )
        except subprocess.TimeoutExpired:
            print(f"\nTimeout no clipe {i}, pulando.")
            return None
        except Exception as e:
            print(f"\nErro ao processar clipe {i}: {e}")
            return None
        
        # Verificar se todos os arquivos foram gerados
        if not (os.path.exists(out_vid) and os.path.exists(out_audio) and os.path.exists(out_img)):
            return None
        
        return i, sub_en, sub_pt, out_vid, out_audio, out_img

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
    
    # ── FASE 2: Upload para o Anki em paralelo ───────────────────────────────
    print(f"Enviando {len(valid_cards)} cards para o Anki (paralelizado)...")
    
    def upload_card(card_data):
        """Upload de mídia + criação de nota para um card."""
        i, sub_en, sub_pt, out_vid, out_audio, out_img = card_data
        vid_filename   = os.path.basename(out_vid)
        audio_filename = os.path.basename(out_audio)
        img_filename   = os.path.basename(out_img)
        
        # Upload dos 3 arquivos de mídia
        invoke_anki('storeMediaFile', filename=vid_filename,   path=os.path.abspath(out_vid))
        invoke_anki('storeMediaFile', filename=audio_filename, path=os.path.abspath(out_audio))
        invoke_anki('storeMediaFile', filename=img_filename,   path=os.path.abspath(out_img))
        
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
        
        res = invoke_anki('addNote', note=note)
        return i, res is not None
    
    # Upload paralelo com até 4 workers (AnkiConnect não lida bem com muitos simultâneos)
    uploaded = 0
    failed = 0
    anki_workers = min(4, len(valid_cards))
    
    with ThreadPoolExecutor(max_workers=anki_workers) as executor:
        future_to_card = {executor.submit(upload_card, card): card[0] for card in valid_cards}
        for future in as_completed(future_to_card):
            idx, success = future.result()
            if success:
                uploaded += 1
            else:
                failed += 1
                print(f"\nFalha ao adicionar card {idx}.")
            print(f"Cards enviados: {uploaded}/{len(valid_cards)}", end="\r")
    
    print(f"\nConcluído: {uploaded} cards adicionados ao Anki, {failed} falhas.")

def format_srt_time_ffmpeg(srt_time):
    return f"{srt_time.hours:02d}:{srt_time.minutes:02d}:{srt_time.seconds:02d}.{srt_time.milliseconds:03d}"


