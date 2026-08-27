import json
import os
import shutil
import sys

def _config_path():
    """Uses the executable folder in build and the project root in development."""
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "config.json")

def load_config():
    config_path = _config_path()
    if not os.path.exists(config_path) and getattr(sys, "frozen", False):
        bundled_config = os.path.join(getattr(sys, "_MEIPASS", ""), "config.json")
        if os.path.isfile(bundled_config):
            shutil.copy2(bundled_config, config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(new_config):
    with open(_config_path(), "w", encoding="utf-8") as f:
        json.dump(new_config, f, indent=2, ensure_ascii=False)
    global CONFIG
    CONFIG.update(new_config)

CONFIG = load_config()
