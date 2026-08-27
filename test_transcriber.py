import math
import os
import time

from auto_anki.transcriber import _normalize_segments, _write_and_validate_srt

class MockSegment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text

def test_normalization():
    print("Testing transcription normalization...")
    
    # Test 1: Normal case
    raw = [MockSegment(0.0, 1.5, "Hello world"), MockSegment(1.5, 3.0, "This is a test")]
    normalized = _normalize_segments(raw, total_duration=5.0)
    assert len(normalized) == 2
    assert normalized[0] == (0, 1500, "Hello world")
    assert normalized[1] == (1500, 3000, "This is a test")
    
    # Test 2: Clamped to duration
    raw = [MockSegment(4.0, 6.0, "End segment")]
    stats = {}
    normalized = _normalize_segments(raw, total_duration=5.0, stats=stats)
    assert len(normalized) == 1
    assert normalized[0] == (4000, 5000, "End segment")
    assert stats.get("clamped_to_duration") == 1
    
    # Test 3: Outside audio
    raw = [MockSegment(6.0, 7.0, "Ghost segment")]
    stats = {}
    try:
        normalized = _normalize_segments(raw, total_duration=5.0, stats=stats)
        assert False, "Should have raised RuntimeError because no valid speech found"
    except RuntimeError as e:
        assert "did not find any valid speech" in str(e)
    assert stats.get("outside_audio") == 1
    
    # Test 4: Missing text
    raw = [MockSegment(0.0, 1.0, " ")]
    try:
        _normalize_segments(raw, total_duration=5.0)
        assert False, "Should fail on missing text"
    except RuntimeError as e:
        assert "without text" in str(e)
        
    # Test 5: Invalid timestamps
    raw = [MockSegment(1.0, 0.5, "Inverted")]
    try:
        _normalize_segments(raw, total_duration=5.0)
        assert False, "Should fail on inverted timestamps"
    except RuntimeError as e:
        assert "empty/inverted interval" in str(e)
        
    print("All normalization tests passed!")

if __name__ == "__main__":
    test_normalization()
