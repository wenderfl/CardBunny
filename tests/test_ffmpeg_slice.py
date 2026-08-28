import os
import shutil
import uuid
import pysrt

from cardbunny import media_processor
from cardbunny.media_processor import slice_and_export_to_anki

def test_slicing():
    print("Testing ffmpeg slicing...")
    
    video_path = os.path.abspath("test_vid.mp4")
    work_dir = os.path.abspath("workspace_test")
    os.makedirs(work_dir, exist_ok=True)
    
    srt_en_path = os.path.join(work_dir, "en.srt")
    srt_pt_path = os.path.join(work_dir, "pt.srt")
    
    with open(srt_en_path, "w", encoding="utf-8") as f:
        f.write("1\n00:00:00,000 --> 00:00:01,000\nHello\n\n2\n00:00:01,000 --> 00:00:02,000\nWorld\n\n")
        
    with open(srt_pt_path, "w", encoding="utf-8") as f:
        f.write("1\n00:00:00,000 --> 00:00:01,000\nOlá\n\n2\n00:00:01,000 --> 00:00:02,000\nMundo\n\n")
        
    # Mock invoke_anki
    def mock_invoke_anki(action, **params):
        if action == "createDeck":
            return True
        elif action == "storeMediaFile":
            return "stored_filename"
        elif action == "addNote":
            return 12345
        elif action == "modelFieldNames":
            return ["Front", "Back"]
        return None
        
    media_processor.invoke_anki = mock_invoke_anki
    
    try:
        slice_and_export_to_anki(
            video_path,
            srt_en_path,
            srt_pt_path,
            "Test Deck",
            work_dir,
            field_mapping={"audio": "Front", "english_subtitle": "Back"}
        )
        print("Slicing test successful!")
    finally:
        pass

if __name__ == "__main__":
    test_slicing()
