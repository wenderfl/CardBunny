import os
from PIL import Image

def get_asset_path(filename):
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", "icons", filename)

def create_link_icon(size=40, color="white"):
    return Image.open(get_asset_path("link_navy.png")).resize((size, size), Image.Resampling.LANCZOS)

def create_deck_icon(size=40, color="white"):
    return Image.open(get_asset_path("deck_white.png")).resize((size, size), Image.Resampling.LANCZOS)

def create_model_icon(size=40, color="white"):
    return Image.open(get_asset_path("model_white.png")).resize((size, size), Image.Resampling.LANCZOS)

def create_upload_icon(size=40, color="white"):
    return Image.open(get_asset_path("upload_white.png")).resize((size, size), Image.Resampling.LANCZOS)

def create_play_icon(size=60, color="white"):
    return Image.open(get_asset_path("play_navy.png")).resize((size, size), Image.Resampling.LANCZOS)

def create_wait_icon(size=60, color="white"):
    return Image.open(get_asset_path("wait_navy.png")).resize((size, size), Image.Resampling.LANCZOS)

def create_settings_icon(size=40, color="white"):
    return Image.open(get_asset_path("settings_navy.png")).resize((size, size), Image.Resampling.LANCZOS)
