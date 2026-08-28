import os
import shutil
import socket
import subprocess
import time
from urllib.parse import urlparse
import pysrt
from openai import OpenAI
from cardbunny.config import CONFIG

import atexit

_omniroute_process = None

def _cleanup_omniroute():
    global _omniroute_process
    if _omniroute_process is not None:
        try:
            print("Terminating OmniRoute process started by this program...")
            if os.name == 'nt':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(_omniroute_process.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                _omniroute_process.terminate()
                _omniroute_process.wait(timeout=5)
        except Exception:
            try:
                _omniroute_process.kill()
            except Exception:
                pass
        _omniroute_process = None

atexit.register(_cleanup_omniroute)

def _endpoint_is_available(base_url, timeout=1.0):
    parsed = urlparse(base_url)
    host = parsed.hostname
    if not host:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def _ensure_local_ai(base_url):
    """Starts local OmniRoute when the configured endpoint is offline."""
    global _omniroute_process

    if _endpoint_is_available(base_url):
        return

    parsed = urlparse(base_url)
    if parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise RuntimeError(f"AI service is not accessible at {base_url}.")

    command = shutil.which("omniroute.cmd") or shutil.which("omniroute")
    if not command:
        raise RuntimeError(
            "OmniRoute is off and the 'omniroute' command was not found. "
            "Install or start OmniRoute before processing."
        )

    port = parsed.port or 20128
    print("Local AI is off. Starting OmniRoute...")
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if os.name == "nt" and command.lower().endswith((".cmd", ".bat")):
        args = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", command]
    else:
        args = [command]
    
    # We don't use --daemon so we can terminate the process when closing the program
    args.extend(["serve", "--no-open", "--no-tray", "--port", str(port)])

    try:
        _omniroute_process = subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=creation_flags
        )
    except OSError as e:
        raise RuntimeError(f"Could not start OmniRoute: {e}") from e

    for _ in range(30):
        if _omniroute_process.poll() is not None:
            raise RuntimeError("OmniRoute terminated prematurely when trying to start.")
        if _endpoint_is_available(base_url):
            print("OmniRoute started and ready to translate.")
            return
        time.sleep(1)
    
    # If it failed after 30 seconds, we clean up
    _cleanup_omniroute()
    raise RuntimeError("OmniRoute was started, but did not become available within 30 seconds.")

def translate_srt(srt_path, work_dir):
    if not srt_path or not os.path.exists(srt_path):
        raise FileNotFoundError(f"Subtitle file not found: {srt_path}")
    
    print("starting translation of subtitles with local AI (Omniroute)...")
    _ensure_local_ai(CONFIG['translation']['base_url'])
    subs = pysrt.open(srt_path, encoding='utf-8')
    
    if len(subs) == 0:
        print("Warning: Empty subtitle file. Check transcription.")
        # Return original file without translation to avoid crash
        translated_srt = os.path.join(work_dir, "translated.srt")
        subs.save(translated_srt, encoding='utf-8')
        return translated_srt
    
    try:
        client = OpenAI(
            base_url=CONFIG['translation']['base_url'],
            api_key=CONFIG['translation']['api_key']
        )
        model = CONFIG['translation']['model']
        target_lang = CONFIG['translation'].get('target_language', 'Brazilian Portuguese (pt-BR)')
    except Exception as e:
        raise RuntimeError(f"Error configuring translation client: {e}") from e
    
    def translate_sub(index_sub_tuple):
        i, sub = index_sub_tuple
        last_error = None
        for attempt in range(1, 4):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": f"You are a highly accurate translator. Translate the given text to {target_lang}. Output ONLY the translated text, without formatting, quotes, explanations, or the original text."},
                        {"role": "user", "content": sub.text}
                    ],
                    temperature=0.1
                )
                translated_text = response.choices[0].message.content.strip()
                if not translated_text:
                    raise ValueError("AI returned an empty translation.")
                sub.text = translated_text
                return None
            except Exception as e:
                last_error = e
                print(f"\nFailed to translate line {i} (attempt {attempt}/3): {e}")

        return f"Could not translate line {i}. The process was interrupted to avoid creating cards with incorrect subtitles. Error: {last_error}"

    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    lock = threading.Lock()
    translated_count = 0
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(translate_sub, (i, sub)): (i, sub) for i, sub in enumerate(subs, 1)}
        for future in as_completed(futures):
            error_msg = future.result()
            if error_msg:
                raise RuntimeError(error_msg)
            
            with lock:
                translated_count += 1
                print(f"Translated line {translated_count}/{len(subs)}", end="\r")

    print()
    translated_srt = os.path.join(work_dir, "translated.srt")
    subs.save(translated_srt, encoding='utf-8')
    print(f"Translation completed: {translated_srt}")
    return translated_srt
