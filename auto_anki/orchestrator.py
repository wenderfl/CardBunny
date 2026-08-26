import os
import shutil
import uuid
from auto_anki.config import CONFIG
from auto_anki.downloader import download_video
from auto_anki.transcriber import transcribe_video
from auto_anki.translator import translate_srt
from auto_anki.media_processor import slice_and_export_to_anki

def run_pipeline(url, local_video=None, local_srt_en=None, local_srt_pt=None, field_mapping=None):
    """
    Executa o pipeline completo de processamento.

    Parâmetros opcionais para substituir etapas automáticas:
      local_video  (str|None): Caminho para vídeo local. Se fornecido, pula o download.
      local_srt_en (str|None): Caminho para legenda em inglês (.srt). Se fornecido, pula a transcrição.
      local_srt_pt (str|None): Caminho para legenda em português (.srt). Se fornecido, pula a tradução.
    """
    # Criar pasta temporária de trabalho (SANDBOXED)
    run_id = uuid.uuid4().hex[:8]
    work_dir = f"workspace_{run_id}"
    os.makedirs(work_dir, exist_ok=True)

    try:
        # Validar entradas antes de copiar/processar. Isso também protege usos via CLI.
        if local_video and not os.path.isfile(local_video):
            raise FileNotFoundError(f"Vídeo local não encontrado: {local_video}")
        if local_srt_en and not os.path.isfile(local_srt_en):
            raise FileNotFoundError(f"Legenda local não encontrada: {local_srt_en}")
        if local_srt_pt and not os.path.isfile(local_srt_pt):
            raise FileNotFoundError(f"Legenda traduzida local não encontrada: {local_srt_pt}")
        if local_srt_en and os.path.splitext(local_srt_en)[1].lower() != ".srt":
            raise ValueError("A legenda original precisa estar no formato .srt.")
        if local_srt_pt and os.path.splitext(local_srt_pt)[1].lower() != ".srt":
            raise ValueError("A legenda traduzida precisa estar no formato .srt.")

        # ── ETAPA 1: Vídeo ──────────────────────────────────────────────────
        if local_video:
            print(f"Usando vídeo local: {os.path.basename(local_video)}")
            # Copiar para o work_dir para manter o sandboxing
            ext = os.path.splitext(local_video)[1]
            dest_video = os.path.join(work_dir, f"video{ext}")
            shutil.copy2(local_video, dest_video)
            video_path = dest_video
        else:
            if not url:
                print("Erro: Nenhuma URL ou vídeo local fornecido.")
                return False, work_dir
            video_path = download_video(url, work_dir)
            if not video_path:
                print("Erro no download.")
                return False, work_dir

        # ── ETAPA 2: Legenda em inglês (transcrição) ─────────────────────────
        if local_srt_en:
            print(f"Usando legenda EN local: {os.path.basename(local_srt_en)}")
            dest_srt_en = os.path.join(work_dir, "original.srt")
            shutil.copy2(local_srt_en, dest_srt_en)
            srt_en = dest_srt_en
        else:
            srt_en = transcribe_video(video_path, work_dir)

        # ── ETAPA 3: Legenda em português (tradução) ─────────────────────────
        if local_srt_pt:
            print(f"Usando legenda PT local: {os.path.basename(local_srt_pt)}")
            dest_srt_pt = os.path.join(work_dir, "translated.srt")
            shutil.copy2(local_srt_pt, dest_srt_pt)
            srt_pt = dest_srt_pt
        else:
            srt_pt = translate_srt(srt_en, work_dir)

        # ── ETAPA 4: Fatiar e exportar para o Anki ───────────────────────────
        selected_mapping = field_mapping or CONFIG.get('field_mappings', {}).get(CONFIG['anki']['model_name'])
        slice_and_export_to_anki(
            video_path, srt_en, srt_pt, CONFIG['anki']['deck_name'], work_dir,
            field_mapping=selected_mapping,
        )
        print("Concluído com sucesso!")
        return True, work_dir

    except Exception as e:
        import traceback
        print(f"\nOcorreu um erro crítico no processo: {e}")
        print(traceback.format_exc())
        return False, work_dir
