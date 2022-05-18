import io
import os

from PIL import Image, ImageDraw, ImageFont


def render_text_to_png(font_file, save_path, text="""Everything is designed. 
Few things are 
designed well""", text_color="#383838",
                       bg_color="#ffffff", spacing=40, font_size=80):
    # Font of label
    label_ttf = os.path.join("fonts/Poppins-Bold.ttf")

    font = ImageFont.truetype(font_file, font_size, encoding='utf-8')
    label_font = ImageFont.truetype(label_ttf, 40, encoding='utf-8')
    # Label tet
    fam, style = font.getname()
    style = f" ({style})" if style != "?" else ""
    label_text = f"- {fam}{style}"

    # Image created just to fetch boundary box for the fonts
    # Other methods failed to account for ascender and descender
    im = Image.new("RGB", (0, 0), "white")
    image_draw = ImageDraw.Draw(im)
    _, _, w, h = image_draw.multiline_textbbox((0, 0), text, font, spacing=spacing)
    _, _, lw, lh = image_draw.multiline_textbbox((0, 0), text, label_font)  # (0, 18, 960, 270)
    im.close()

    padding = 100

    # We're going for a 3 by 2 aspect ratio
    # but if that will result in clipping, we just use height or width
    # with specified padding
    if w > h:
        # since width > height we use 3 by 2 ratio
        width = w + (padding * 2)
        if (2 / 3) * w > h:  # clipping wouldn't occur
            height = (2 / 3 * (width - padding * 2)) + padding * 2
        else:
            height = h + (padding * 2)
    elif w < h:
        # since height > width we use 2 by 3 ratio
        height = h + (padding * 2)
        if (2 / 3) * h > w:
            width = (2 / 3 * (height - padding * 2)) + lh * 2
        else:
            width = w + (padding * 2)
    else:  # Both equal - discard aspect ratio
        width = w + (padding * 2)
        height = h + (padding * 2)

    # Image
    # Added some space to h for label text
    image = Image.new("RGBA", (round(width), round(height + lh / 2)), bg_color)
    draw = ImageDraw.Draw(image)
    # Positioning
    pos = (width - w) / 2, (height - h) / 2
    top_to_font_bottom = ((height - h) / 2 + h)
    label_pos = (width - w) / 2, top_to_font_bottom + padding

    draw.multiline_text(pos, text, text_color, font=font, spacing=spacing)
    draw.text(label_pos, label_text, text_color, font=label_font)
    # Save png file
    image.load()
    image.save(save_path)
