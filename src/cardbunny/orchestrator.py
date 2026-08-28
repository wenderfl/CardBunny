import os
import shutil
import uuid
from cardbunny.config import CONFIG
from cardbunny.downloader import download_video
from cardbunny.transcriber import transcribe_video
from cardbunny.translator import translate_srt
from cardbunny.media_processor import slice_and_export_to_anki

def run_pipeline(url, local_video=None, local_srt_en=None, local_srt_pt=None, field_mapping=None):
    """
    Executes the complete processing pipeline.

    Optional parameters to replace automatic steps:
      local_video  (str|None): Path to local video. If provided, skips download.
      local_srt_en (str|None): Path to English subtitle (.srt). If provided, skips transcription.
      local_srt_pt (str|None): Path to translated subtitle (.srt). If provided, skips translation.
    """
    # Create temporary work folder (SANDBOXED)
    run_id = uuid.uuid4().hex[:8]
    work_dir = f"workspace_{run_id}"
    os.makedirs(work_dir, exist_ok=True)

    try:
        # Validate inputs before copying/processing. This also protects CLI usage.
        if local_video and not os.path.isfile(local_video):
            raise FileNotFoundError(f"Local video not found: {local_video}")
        if local_srt_en and not os.path.isfile(local_srt_en):
            raise FileNotFoundError(f"Local subtitle not found: {local_srt_en}")
        if local_srt_pt and not os.path.isfile(local_srt_pt):
            raise FileNotFoundError(f"Local translated subtitle not found: {local_srt_pt}")
        if local_srt_en and os.path.splitext(local_srt_en)[1].lower() != ".srt":
            raise ValueError("The original subtitle must be in .srt format.")
        if local_srt_pt and os.path.splitext(local_srt_pt)[1].lower() != ".srt":
            raise ValueError("The translated subtitle must be in .srt format.")

        # ── STEP 1: Video ──────────────────────────────────────────────────
        if local_video:
            print(f"Using local video: {os.path.basename(local_video)}")
            # Copy to work_dir to keep sandboxing
            ext = os.path.splitext(local_video)[1]
            dest_video = os.path.join(work_dir, f"video{ext}")
            shutil.copy2(local_video, dest_video)
            video_path = dest_video
        else:
            if not url:
                print("Error: No URL or local video provided.")
                return False, work_dir
            video_path = download_video(url, work_dir)
            if not video_path:
                print("Download error.")
                return False, work_dir

        # ── STEP 2: English subtitle (transcription) ─────────────────────────
        if local_srt_en:
            print(f"Using local EN subtitle: {os.path.basename(local_srt_en)}")
            dest_srt_en = os.path.join(work_dir, "original.srt")
            shutil.copy2(local_srt_en, dest_srt_en)
            srt_en = dest_srt_en
        else:
            srt_en = transcribe_video(video_path, work_dir)

        # ── STEP 3: Translated subtitle (translation) ─────────────────────────
        if local_srt_pt:
            print(f"Using local translated subtitle: {os.path.basename(local_srt_pt)}")
            dest_srt_pt = os.path.join(work_dir, "translated.srt")
            shutil.copy2(local_srt_pt, dest_srt_pt)
            srt_pt = dest_srt_pt
        else:
            srt_pt = translate_srt(srt_en, work_dir)

        # ── STEP 4: Slice and export to Anki ───────────────────────────
        selected_mapping = field_mapping or CONFIG.get('field_mappings', {}).get(CONFIG['anki']['model_name'])
        slice_and_export_to_anki(
            video_path, srt_en, srt_pt, CONFIG['anki']['deck_name'], work_dir,
            field_mapping=selected_mapping,
        )
        print("Completed successfully!")
        return True, work_dir

    except Exception as e:
        import traceback
        print(f"\nA critical error occurred in the process: {e}")
        print(traceback.format_exc())
        return False, work_dir
