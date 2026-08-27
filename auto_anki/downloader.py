import os
import re
import glob
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

def is_valid_youtube_url(url):
    """Validates if the URL looks like YouTube before trying to download."""
    pattern = re.compile(
        r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w-]+'
    )
    return bool(pattern.search(url))

def download_video(url, output_dir):
    # Clean URL (remove spaces, newlines, and duplicate URLs)
    url = url.strip()
    
    # Detect and fix duplicate pasted URLs (e.g. https://...https://...)
    if url.count('http') > 1:
        # Take only the first URL
        match = re.search(r'https?://[^\s]+', url)
        if match:
            url = match.group(0)
            print(f"Duplicate URL detected. Using: {url}")
    
    if not is_valid_youtube_url(url):
        print(f"Error: The provided URL does not seem to be from YouTube: '{url}'")
        return None
    
    print(f"Downloading video from {url}...")
    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best',
        'outtmpl': os.path.join(output_dir, 'video.%(ext)s'),
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': False
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            if not info_dict:
                print("Error: yt-dlp did not return video information.")
                return None
            
            # Fail-safe rescue: grab any 'video.*' file that isn't temporary
            video_files = [f for f in glob.glob(os.path.join(output_dir, "video.*")) if not f.endswith('.part') and not f.endswith('.ytdl')]
            
            if video_files:
                return video_files[0]
            print("Error: Video file not found after download.")
            return None
            
    except DownloadError as e:
        msg = str(e)
        if "Private video" in msg:
            print("Error: This video is private and cannot be downloaded.")
        elif "Video unavailable" in msg or "unavailable" in msg.lower():
            print("Error: This video is unavailable (might have been removed).")
        elif "HTTP Error 429" in msg:
            print("Error: Too many requests to YouTube. Wait a few minutes and try again.")
        else:
            print(f"Error downloading video: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error in download: {e}")
        return None

