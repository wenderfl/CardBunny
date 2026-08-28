import os
import sys
import time
from PIL import ImageGrab, Image

# Setup path so it can import our modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import customtkinter as ctk
from ui.app import CardBunnyApp

def main():
    root = ctk.CTk()
    app = CardBunnyApp(root)
    
    # Ensure window is visible and updated
    root.update()
    root.deiconify()
    
    # Wait a moment for it to render fully on Windows
    time.sleep(1.0)
    root.update()
    
    # Get window coordinates
    x = root.winfo_rootx()
    y = root.winfo_rooty()
    w = root.winfo_width()
    h = root.winfo_height()
    
    # Ensure coordinates are valid (not minimized)
    if w <= 1 or h <= 1:
        print("Window not visible enough.")
        root.destroy()
        return
        
    print(f"Grabbing window at {x}, {y}, {w}x{h}")
    
    assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'assets'))
    os.makedirs(assets_dir, exist_ok=True)
    
    frames = []
    
    # 1. Take initial static screenshot
    time.sleep(0.5)
    root.update()
    img_static = ImageGrab.grab(bbox=(x, y, x+w, y+h))
    img_static.save(os.path.join(assets_dir, "ui.png"))
    print("Saved ui.png")
    frames.append(img_static)
    
    # 2. Simulate some interactions for GIF
    app.url_var.set("https://youtube.com/watch?v=mock")
    root.update()
    time.sleep(0.5)
    frames.append(ImageGrab.grab(bbox=(x, y, x+w, y+h)))
    
    app.deck_cb.set("My Deck")
    root.update()
    time.sleep(0.5)
    frames.append(ImageGrab.grab(bbox=(x, y, x+w, y+h)))
    
    # Start fake processing
    def fake_process():
        app._processing = True
        app.set_status("INITIALIZING...", progress=0.1, step=1)
        root.update()
        frames.append(ImageGrab.grab(bbox=(x, y, x+w, y+h)))
        time.sleep(0.5)
        
        app.set_status("TRANSCRIBING...", progress=0.4, step=2)
        app.append_log("> Downloading model...")
        root.update()
        frames.append(ImageGrab.grab(bbox=(x, y, x+w, y+h)))
        time.sleep(0.5)
        
        app.set_status("SLICING MEDIA...", progress=0.7, step=3)
        app.append_log("> Generating WebM clips...")
        root.update()
        frames.append(ImageGrab.grab(bbox=(x, y, x+w, y+h)))
        time.sleep(0.5)
        
        app.set_status("SYNCING TO ANKI...", progress=0.9, step=4)
        app.append_log("> Sending 5 notes...")
        root.update()
        frames.append(ImageGrab.grab(bbox=(x, y, x+w, y+h)))
        time.sleep(0.5)
        
        app.set_status("DONE!", progress=1.0)
        app.append_log("> Success.")
        app._processing = False
        root.update()
        frames.append(ImageGrab.grab(bbox=(x, y, x+w, y+h)))
        time.sleep(0.5)
        
        # Save GIF
        gif_path = os.path.join(assets_dir, "ui_demo.gif")
        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            duration=600, # 600ms per frame
            loop=0
        )
        print(f"Saved {gif_path}")
        root.destroy()
        
    root.after(500, fake_process)
    root.mainloop()

if __name__ == "__main__":
    main()
