from PIL import Image, ImageDraw

def create_link_icon(size=40, color="white"):
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # Desenha as argolas de um "link"
    draw.arc([10, 15, 20, 25], start=0, end=360, fill=color, width=2)
    draw.arc([20, 15, 30, 25], start=0, end=360, fill=color, width=2)
    draw.line([18, 20, 22, 20], fill=color, width=2)
    return img

def create_deck_icon(size=40, color="white"):
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # Caixa / Fichário
    draw.rectangle([10, 12, 30, 28], outline=color, width=2)
    draw.line([10, 18, 30, 18], fill=color, width=2)
    return img

def create_model_icon(size=40, color="white"):
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # Documento de texto (Nota)
    draw.rectangle([12, 8, 28, 32], outline=color, width=2)
    draw.line([16, 14, 24, 14], fill=color, width=2)
    draw.line([16, 19, 24, 19], fill=color, width=2)
    draw.line([16, 24, 20, 24], fill=color, width=2)
    return img

def create_play_icon(size=60, color="white"):
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # Triângulo puro (Play)
    draw.polygon([(20, 15), (20, 45), (45, 30)], fill=color)
    return img

def create_wait_icon(size=60, color="white"):
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # Ampulheta genérica
    draw.polygon([(18, 15), (42, 15), (30, 30)], fill=color)
    draw.polygon([(18, 45), (42, 45), (30, 30)], fill=color)
    return img

def create_settings_icon(size=40, color="white"):
    """Cria um ícone de engrenagem simples, sem depender de arquivos externos."""
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    center = size // 2
    outer = max(8, size // 3)
    inner = max(3, size // 9)
    draw.ellipse(
        [center - outer, center - outer, center + outer, center + outer],
        outline=color,
        width=max(2, size // 14),
    )
    draw.ellipse(
        [center - inner, center - inner, center + inner, center + inner],
        outline=color,
        width=max(2, size // 16),
    )
    tooth_width = max(2, size // 12)
    for x1, y1, x2, y2 in (
        (center, 3, center, center - outer + 2),
        (center, center + outer - 2, center, size - 3),
        (3, center, center - outer + 2, center),
        (center + outer - 2, center, size - 3, center),
    ):
        draw.line([x1, y1, x2, y2], fill=color, width=tooth_width)
    return img
