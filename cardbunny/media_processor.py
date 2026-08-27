import os
import subprocess
import json
import shutil
import threading
import uuid
import pysrt
from concurrent.futures import ThreadPoolExecutor, as_completed
from cardbunny.config import CONFIG
from cardbunny.anki_client import invoke_anki
from cardbunny.mapper import map_fields

# Detect number of available CPUs to adjust parallelism automatically
_CPU_COUNT = os.cpu_count() or 4

def _get_worker_count():
    return max(1, _CPU_COUNT // 2)

def _probe_media(video_path):
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if not ffmpeg_path or not ffprobe_path:
        raise RuntimeError("FFmpeg and FFprobe must be available in PATH.")
    try:
        result = subprocess.run(
            [ffprobe_path, "-v", "error", "-show_streams", "-show_format", "-of", "json", video_path],
            capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFprobe failed to analyze video: {result.stderr.strip()[-500:]}")
        metadata = json.loads(result.stdout)
        streams = metadata.get("streams", [])
        if not any(stream.get("codec_type") == "video" for stream in streams):
            raise RuntimeError("The selected file does not have a video track.")
        if not any(stream.get("codec_type") == "audio" for stream in streams):
            raise RuntimeError("The selected file does not have an audio track.")
        duration = float(metadata.get("format", {}).get("duration", 0))
        if duration <= 0:
            raise RuntimeError("Could not determine video duration.")
        return ffmpeg_path, duration
    except (ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Invalid metadata returned by FFprobe: {error}") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("FFprobe exceeded time limit when analyzing the video.") from error

def _validate_subtitles(subs_en, subs_pt, video_duration):
    if not subs_en:
        raise RuntimeError("The original transcription does not contain any speech.")
    if len(subs_en) != len(subs_pt):
        raise RuntimeError(
            f"The subtitles are misaligned: {len(subs_en)} original segments and "
            f"{len(subs_pt)} translations."
        )
    duration_ms = round(video_duration * 1000)
    for index, (sub_en, sub_pt) in enumerate(zip(subs_en, subs_pt), start=1):
        start_ms, end_ms = sub_en.start.ordinal, sub_en.end.ordinal
        if not sub_en.text.strip() or not sub_pt.text.strip():
            raise RuntimeError(f"Segment {index} has empty original or translated text.")
        if start_ms < 0 or end_ms <= start_ms:
            raise RuntimeError(f"Segment {index} has invalid timestamps.")
        if start_ms >= duration_ms or end_ms > duration_ms + 500:
            raise RuntimeError(
                f"Segment {index} ends outside the video "
                f"({end_ms / 1000:.3f}s > {video_duration:.3f}s)."
            )
        if (abs(sub_pt.start.ordinal - start_ms) > 500 or
                abs(sub_pt.end.ordinal - end_ms) > 500):
            raise RuntimeError(f"Translated segment {index} does not match the original interval.")

def slice_and_export_to_anki(video_path, srt_en, srt_pt, deck_name, work_dir, field_mapping=None):
    print(f"slicing and exporting to Anki...") # Must match app.py exact log sniffer key!
    print(f"Configured parallelism: {_get_worker_count()} workers on {_CPU_COUNT} available cores.")
    
    ffmpeg_path, video_duration = _probe_media(video_path)
    
    # Map model fields automatically
    dynamic_fields = field_mapping or map_fields(CONFIG['anki']['model_name'])
    if not dynamic_fields:
        raise RuntimeError("Failed to map Anki model fields.")
    
    subs_en = pysrt.open(srt_en, encoding='utf-8')
    subs_pt = pysrt.open(srt_pt, encoding='utf-8')

    _validate_subtitles(subs_en, subs_pt, video_duration)

    if invoke_anki('createDeck', deck=deck_name) is None:
        raise RuntimeError("Could not create or access the Anki deck.")
    
    output_dir = os.path.join(work_dir, "slices")
    os.makedirs(output_dir, exist_ok=True)
    
    base_name = "vid_" + uuid.uuid4().hex[:12]
    creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    
    # Number of threads each ffmpeg can use internally
    # With many workers, we use fewer threads per ffmpeg to avoid saturation
    ffmpeg_threads = max(1, min(4, _CPU_COUNT // _get_worker_count()))
    
    def process_media(args):
        """
        Processes a single clip using a SINGLE ffmpeg call with multiple outputs.
        
        Optimizations:
        - 1 ffmpeg call → mp4 + mp3 + jpg (instead of 3 separate calls)
        - Snapshot extracted directly from original video
        - Fast seek: -ss before -i (stream copy up to point)
        - Dynamically configured threads per process
        """
        i, sub_en, sub_pt = args
        start_sec = sub_en.start.ordinal / 1000.0
        end_sec = min(sub_en.end.ordinal / 1000.0, video_duration)
        delta_sec = end_sec - start_sec
        
        if delta_sec <= 0:
            return None
        
        out_vid   = os.path.join(output_dir, f"{base_name}_{i}.mp4")
        out_audio = os.path.join(output_dir, f"{base_name}_{i}.mp3")
        out_img   = os.path.join(output_dir, f"{base_name}_{i}.jpg")
        
        # ─── SINGLE FFMPEG CALL with 3 outputs ───────────────────────────
        # -ss before -i: fast seek (decodes only from nearest keyframe)
        # -t limits duration
        # Output 1: MP4 with libx264 (video) + aac (audio)
        # Output 2: MP3 with libmp3lame
        # Output 3: JPEG from middle frame, directly from original video
        cmd = [
            ffmpeg_path, "-y",
            "-threads", str(ffmpeg_threads),    # global threads for the process
            "-ss", str(start_sec),              # fast seek BEFORE input
            "-i", video_path,
            "-t", str(delta_sec),
            
            # --- Output 1: MP4 (video + audio) ---
            "-map", "0:v:0",
            "-map", "0:a:0",
            "-c:v", "libx264",
            "-preset", "ultrafast",             # extreme speed mode
            "-crf", "28",                       # acceptable quality
            "-c:a", "aac",
            "-b:a", "128k",
            "-vf", "scale=-2:360",              # 360p is enough for studying — 4x faster
            out_vid,
            
            # --- Output 2: MP3 (audio) ---
            "-t", str(delta_sec),              # each output needs its own limit
            "-map", "0:a:0",
            "-c:a", "libmp3lame",
            "-q:a", "4",                        # VBR quality (0=best, 9=worst), 4≈128kbps
            out_audio,
            
            # --- Output 3: JPEG (snapshot from middle of clip) ---
            "-ss", str(delta_sec / 2.0),
            "-map", "0:v:0",
            "-vf", "scale=-2:360",
            "-vframes", "1",
            "-q:v", "5",                        # JPEG quality (2=high, 10=low)
            out_img,
        ]
        
        for attempt in range(1, 3):
            if attempt == 2:
                try:
                    # Fallback to first frame if middle frame extraction fails
                    idx = cmd.index("-ss", cmd.index(out_audio))
                    cmd.pop(idx)
                    cmd.pop(idx)
                except ValueError:
                    pass
                    
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
                    f"\nFFmpeg failed on clip {i} "
                    f"(attempt {attempt}/2, code {completed.returncode}): "
                    f"{completed.stderr.decode(errors='replace').strip()[-300:]}"
                )
            except subprocess.TimeoutExpired:
                print(f"\nTimeout on clip {i} (attempt {attempt}/2).")
            except Exception as e:
                print(f"\nError on clip {i} (attempt {attempt}/2): {e}")
        return None

    # ── PHASE 1: Parallel media generation ─────────────────────────────────
    tasks = [(i, sub_en, sub_pt) for i, (sub_en, sub_pt) in enumerate(zip(subs_en, subs_pt))]
    total = len(tasks)
    valid_cards = [None] * total  # pre-allocate to keep order
    generated = 0
    lock = threading.Lock()
    
    print(f"Generating {total} clips in parallel ({_get_worker_count()} workers)...")
    
    with ThreadPoolExecutor(max_workers=_get_worker_count()) as executor:
        future_to_idx = {executor.submit(process_media, task): task[0] for task in tasks}
        for future in as_completed(future_to_idx):
            result = future.result()
            if result:
                valid_cards[result[0]] = result
                with lock:
                    generated += 1
                print(f"Generated clips: {generated}/{total}", end="\r")
    
    # Filter nulls and preserve subtitle order
    valid_cards = [c for c in valid_cards if c is not None]
    print(f"\n{len(valid_cards)}/{total} clips generated successfully.")
    if len(valid_cards) != total:
        missing = total - len(valid_cards)
        raise RuntimeError(
            f"{missing} clip(s) could not be generated. Export was interrupted "
            "to avoid creating a deck with missing transcripts."
        )
    
    # ── PHASE 2: Upload to Anki in parallel ───────────────────────────────
    print(f"Sending {len(valid_cards)} cards to Anki (parallelized)...")
    
    def upload_card(card_data):
        """Media upload + note creation for a card."""
        i, sub_en, sub_pt, out_vid, out_audio, out_img = card_data
        vid_filename   = os.path.basename(out_vid)
        audio_filename = os.path.basename(out_audio)
        img_filename   = os.path.basename(out_img)
        
        # Upload of the 3 media files
        stored_media = (
            invoke_anki('storeMediaFile', filename=vid_filename, path=os.path.abspath(out_vid)),
            invoke_anki('storeMediaFile', filename=audio_filename, path=os.path.abspath(out_audio)),
            invoke_anki('storeMediaFile', filename=img_filename, path=os.path.abspath(out_img)),
        )
        if any(result is None for result in stored_media):
            return i, None, "failed to upload one or more media files"
        
        fields = {}
        # Audio: [sound:vid_...mp3] — MP3 audio file with [sound:] tag
        if dynamic_fields.get('audio'):
            fields[dynamic_fields['audio']] = f"[sound:{audio_filename}]"
        # Clip: vid_...mp4 — only the MP4 video filename (without [sound:] tag)
        if dynamic_fields.get('clip'):
            fields[dynamic_fields['clip']] = vid_filename
        # Snapshot: <img src="vid_...jpg"> — scene frame image
        if dynamic_fields.get('snapshot'):
            fields[dynamic_fields['snapshot']] = f'<img src="{img_filename}">'
        # English subtitle (original text)
        if dynamic_fields.get('english_subtitle'):
            fields[dynamic_fields['english_subtitle']] = sub_en.text
        # Portuguese subtitle (translated text)
        if dynamic_fields.get('portuguese_subtitle'):
            fields[dynamic_fields['portuguese_subtitle']] = sub_pt.text
        # Index: [sound:vid_...mp4] — MP4 video file with [sound:] tag
        if dynamic_fields.get('index'):
            fields[dynamic_fields['index']] = f"[sound:{vid_filename}]"
        
        note = {
            "deckName": deck_name,
            "modelName": CONFIG['anki']['model_name'],
            "fields": fields,
            "options": {"allowDuplicate": True, "duplicateScope": "deck"},
            "tags": ["cardbunny"]
        }
        
        note_id = invoke_anki('addNote', note=note)
        if note_id is None:
            return i, None, "failed to create note"
        return i, note_id, None
    
    # Parallel upload with up to 4 workers (AnkiConnect does not handle many simultaneous well)
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
                print(f"\nFailed to add card {idx}: {error}.")
            print(f"Cards sent: {uploaded}/{len(valid_cards)}", end="\r")

    if failed:
        print("\nUpload failed. Reverting notes and media from this execution...")
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
            f"{failed} card(s) failed upload. Notes from this execution were reverted."
        )

    print(f"\nDone: {uploaded} cards added to Anki, {failed} failures.")
