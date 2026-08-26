import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_EXPERIMENTAL_WARNING"] = "1"

import sys
import multiprocessing
from ui.app import launch_gui

def main():
    multiprocessing.freeze_support()
    # Opcional: Permitir ainda uso por linha de comando
    if len(sys.argv) == 2:
        from auto_anki.orchestrator import run_pipeline
        url = sys.argv[1]
        run_pipeline(url)
    else:
        # Se clicar no run.bat sem argumentos (novo padrão) abre a GUI
        launch_gui()

if __name__ == "__main__":
    main()
