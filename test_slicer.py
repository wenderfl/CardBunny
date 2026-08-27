import os
import pysrt
import uuid
from auto_anki.media_processor import _validate_subtitles

def test_slicer_validation():
    print("Testing media_processor subtitle validation...")
    
    class MockItem:
        def __init__(self, ordinal):
            self.ordinal = ordinal
            
    class MockSub:
        def __init__(self, start_ms, end_ms, text):
            self.start = MockItem(start_ms)
            self.end = MockItem(end_ms)
            self.text = text
            
    # Test normal
    subs_en = [MockSub(0, 1500, "Hello")]
    subs_pt = [MockSub(0, 1500, "Olá")]
    _validate_subtitles(subs_en, subs_pt, 5.0)
    
    # Test misaligned
    try:
        _validate_subtitles(subs_en, [MockSub(0, 1500, "Olá"), MockSub(1500, 3000, "Teste")], 5.0)
        assert False, "Should fail on misaligned"
    except RuntimeError as e:
        assert "misaligned" in str(e)
        
    # Test empty text
    try:
        _validate_subtitles([MockSub(0, 1500, "  ")], subs_pt, 5.0)
        assert False, "Should fail on empty text"
    except RuntimeError as e:
        assert "empty original or translated" in str(e)
        
    # Test ends outside video
    try:
        _validate_subtitles([MockSub(0, 6000, "Hello")], [MockSub(0, 6000, "Olá")], 5.0)
        assert False, "Should fail on outside video"
    except RuntimeError as e:
        assert "ends outside the video" in str(e)
        
    print("All slicer validation tests passed!")

if __name__ == "__main__":
    test_slicer_validation()
