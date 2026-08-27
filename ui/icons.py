from PIL import Image, ImageDraw

def create_link_icon(size=40, color="white"):
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # Draws the rings of a 'link'
    draw.arc([10, 15, 20, 25], start=0, end=360, fill=color, width=2)
    draw.arc([20, 15, 30, 25], start=0, end=360, fill=color, width=2)
    draw.line([18, 20, 22, 20], fill=color, width=2)
    return img

def create_deck_icon(size=40, color="white"):
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # Box / Binder
    draw.rectangle([10, 12, 30, 28], outline=color, width=2)
    draw.line([10, 18, 30, 18], fill=color, width=2)
    return img

def create_model_icon(size=40, color="white"):
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # Text document (Note)
    draw.rectangle([12, 8, 28, 32], outline=color, width=2)
    draw.line([16, 14, 24, 14], fill=color, width=2)
    draw.line([16, 19, 24, 19], fill=color, width=2)
    draw.line([16, 24, 20, 24], fill=color, width=2)
    return img

def create_play_icon(size=60, color="white"):
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # Pure triangle (Play)
    draw.polygon([(20, 15), (20, 45), (45, 30)], fill=color)
    return img

def create_wait_icon(size=60, color="white"):
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # Generic hourglass
    draw.polygon([(18, 15), (42, 15), (30, 30)], fill=color)
    draw.polygon([(18, 45), (42, 45), (30, 30)], fill=color)
    return img

def create_settings_icon(size=40, color="white"):
    """Creates a gear icon using PIL."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    draw_mask = ImageDraw.Draw(mask)
    import math
    
    cx, cy = size // 2, size // 2
    r_outer = size // 3 + 1
    r_inner = r_outer - 4
    
    num_teeth = 8
    thickness = 6
    for i in range(num_teeth):
        angle = math.radians(i * (360 / num_teeth))
        length = r_outer + 3
        x1 = cx + length * math.cos(angle)
        y1 = cy + length * math.sin(angle)
        x2 = cx - length * math.cos(angle)
        y2 = cy - length * math.sin(angle)
        draw_mask.line([x1, y1, x2, y2], fill=255, width=thickness)
    
    draw_mask.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], fill=255)
    draw_mask.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner], fill=0)
    
    img_color = Image.new("RGBA", (size, size), color)
    img.paste(img_color, (0, 0), mask=mask)
    return img
