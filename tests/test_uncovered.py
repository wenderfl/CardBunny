from cardbunny.transcriber import _recover_uncovered_speech

class MockModel:
    def transcribe(self, *args, **kwargs):
        # Simulate whisper finding NO text in the noise region
        return [], None

def test_recover_empty():
    model = MockModel()
    video_path = "dummy.mp4"
    segments = [(0, 1000, "Hello")]
    uncovered = [(2000, 3000)] # 1 second of "speech" (actually noise)
    
    try:
        _recover_uncovered_speech(model, video_path, segments, uncovered)
        print("Success! It did not crash.")
    except Exception as e:
        print(f"CRASHED! Bug found: {e}")

if __name__ == "__main__":
    test_recover_empty()
