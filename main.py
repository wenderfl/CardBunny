import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_EXPERIMENTAL_WARNING"] = "1"

import sys
import multiprocessing
import sys
import platform
import ctypes

if platform.system() == "Windows":
    try:
        myappid = 'automoviesanki.app.version1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

import atexit
from ui.app import launch_gui

def _force_cleanup_children():
    """Aggressively ensures no child processes (ffmpeg, omniroute, etc.) survive."""
    if os.name == 'nt':
        try:
            import subprocess
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(os.getpid())], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except Exception:
            pass

def main():
    atexit.register(_force_cleanup_children)
    multiprocessing.freeze_support()
    # Optional: Allow command-line usage
    if len(sys.argv) == 2:
        from auto_anki.orchestrator import run_pipeline
        url = sys.argv[1]
        run_pipeline(url)
    else:
        # If run.bat is clicked without arguments, open the GUI
        launch_gui()

if __name__ == "__main__":
    main()
