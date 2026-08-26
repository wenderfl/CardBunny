import json

def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(new_config):
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(new_config, f, indent=2, ensure_ascii=False)
    global CONFIG
    CONFIG.update(new_config)

CONFIG = load_config()
