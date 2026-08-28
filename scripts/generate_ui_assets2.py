import os
import sys
from PIL import ImageGrab, Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import customtkinter as ctk
from ui.app import CardBunnyApp

def main():
    root = ctk.CTk()
    app = CardBunnyApp(root)
    root.update()
    root.deiconify()
    
    # We will use root.after to advance states and take screenshots
    frames = []
    
    assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'assets'))
    os.makedirs(assets_dir, exist_ok=True)
    
    def grab():
        x = root.winfo_rootx()
        y = root.winfo_rooty()
        w = root.winfo_width()
        h = root.winfo_height()
        if w > 1 and h > 1:
            return ImageGrab.grab(bbox=(x, y, x+w, y+h))
        return None

    def step1():
        img = grab()
        if img:
            img.save(os.path.join(assets_dir, "ui.png"))
            frames.append(img)
            print("Saved ui.png")
        app.url_var.set("https://youtube.com/watch?v=mock")
        root.after(400, step2)

    def step2():
        img = grab()
        if img: frames.append(img)
        app.deck_cb.set("My Deck")
        root.after(400, step3)

    def step3():
        img = grab()
        if img: frames.append(img)
        app._processing = True
        app.set_status("INITIALIZING...", progress=0.1, step=1)
        root.after(400, step4)

    def step4():
        img = grab()
        if img: frames.append(img)
        app.set_status("TRANSCRIBING...", progress=0.4, step=2)
        app.append_log("> Downloading model...")
        root.after(400, step5)
        
    def step5():
        img = grab()
        if img: frames.append(img)
        app.set_status("SLICING MEDIA...", progress=0.7, step=3)
        app.append_log("> Generating WebM clips...")
        root.after(400, step6)
        
    def step6():
        img = grab()
        if img: frames.append(img)
        app.set_status("SYNCING TO ANKI...", progress=0.9, step=4)
        app.append_log("> Sending 5 notes...")
        root.after(400, step7)
        
    def step7():
        img = grab()
        if img: frames.append(img)
        app.set_status("DONE!", progress=1.0)
        app.append_log("> Success.")
        app._processing = False
        root.after(400, finish)
        
    def finish():
        img = grab()
        if img: frames.append(img)
        
        if len(frames) > 0:
            gif_path = os.path.join(assets_dir, "ui_demo.gif")
            frames[0].save(
                gif_path,
                save_all=True,
                append_images=frames[1:],
                duration=400,
                loop=0
            )
            print(f"Saved {gif_path}")
        root.destroy()
        
    root.after(1000, step1)
    root.mainloop()

if __name__ == "__main__":
    main()
