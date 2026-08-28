from PIL import Image, ImageDraw, ImageFont
import os

assets_dir = r"c:\dev\Auto Movies Anki\assets"
ui_path = os.path.join(assets_dir, "ui.png")
gif_path = os.path.join(assets_dir, "ui_demo.gif")

if not os.path.exists(ui_path):
    print("ui.png not found")
    exit(1)

base_img = Image.open(ui_path).convert("RGB")

frames = []
# Create a simple animation: a pulsing overlay or progress bar
for i in range(10):
    frame = base_img.copy()
    draw = ImageDraw.Draw(frame)
    # Draw a simple animated progress bar at the bottom
    bar_width = int(frame.width * (i / 9.0))
    draw.rectangle([0, frame.height - 10, bar_width, frame.height], fill="#6253cc")
    
    # Optional: Draw some text
    if i % 2 == 0:
        draw.text((20, 20), "CardBunny Processing...", fill="#101544")
        
    frames.append(frame)

frames[0].save(
    gif_path,
    save_all=True,
    append_images=frames[1:],
    duration=200,
    loop=0
)
print("Created ui_demo.gif")
