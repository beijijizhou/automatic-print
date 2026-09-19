"""Bounded preview pixels, with production geometry and production badge rendering."""
from PIL import Image, ImageDraw
from ....layout_engine.labeling.base.dynamic_label import source_label_badge
from ....layout_engine.labeling.platform.platform_label import placement_badge, platform_text


def render_example(path, item, labels, settings):
    from dataclasses import replace
    top = min(0,item.block_ry)
    item = replace(item, image_ry=item.image_ry-top, block_ry=item.block_ry-top,
                   label_ry=item.label_ry-top, platform_ry=item.platform_ry-top,
                   footprint_height=item.footprint_height-top)
    scale = min(900/item.footprint_width, 650/item.footprint_height)
    width, height = max(1, round(item.footprint_width*scale)), max(1, round(item.footprint_height*scale))
    canvas = Image.new('RGBA', (width, height), 'white')
    draw = ImageDraw.Draw(canvas)
    for y in range(0, height, 12):
        for x in range(0, width, 12):
            if (x//12+y//12)%2:
                draw.rectangle((x, y, x+11, y+11), fill='#e2e8f0')

    def paste(image, x, y, w, h):
        resized = image.resize((max(1, round(w*scale)), max(1, round(h*scale))), Image.Resampling.LANCZOS)
        canvas.alpha_composite(resized, (round(x*scale), round(y*scale)))
        resized.close()

    with Image.open(path) as source:
        with source.convert('RGBA') as rgba:
            with rgba.rotate(item.rotation_degrees, expand=True) as rotated:
                paste(rotated, item.image_rx, item.image_ry, item.width, item.height)
    if item.label_width:
        badge = source_label_badge(labels[item.index], settings, path, item.rotation_degrees)
        paste(badge, item.label_rx, item.label_ry, item.label_width, item.label_height)
        badge.close()
    if item.platform_width:
        badge = placement_badge(
            platform_text(path, settings), item.platform_width,
            item.platform_height, item.rotation_degrees,
        )
        paste(badge, item.platform_rx, item.platform_ry, item.platform_width, item.platform_height)
        badge.close()
    if item.block_width:
        x, y = item.block_rx*scale, item.block_ry*scale
        draw.rectangle((round(x), round(y), round((item.block_rx+item.block_width)*scale)-1,
                        round((item.block_ry+item.block_height)*scale)-1), fill=settings.color_block_color)
    pixels = canvas.tobytes()
    canvas.close()
    return pixels, (width, height)


def render_direction_diagram(path, degrees):
    """Show source/card orientation when production-safe badge coordinates fail."""
    with Image.open(path) as source:
        with source.convert('RGBA') as rgba:
            rotated = rgba.rotate(degrees, expand=True)
    scale = min(780/rotated.width, 570/rotated.height)
    width, height = max(1, round(rotated.width*scale)), max(1, round(rotated.height*scale))
    canvas = Image.new('RGBA', (width+90, height+60), '#f1f5f9')
    with rotated.resize((width, height), Image.Resampling.LANCZOS) as shown:
        canvas.alpha_composite(shown, (80, 50))
    rotated.close()
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((80, 50, 80+width-1, 50+height-1), outline='#2563eb', width=2)
    draw.rectangle((18, 54, 48, 114), fill='#dc2626')
    draw.text((12, 15), 'DIRECTION ONLY - NOT PRINTABLE', fill='#9a3412')
    pixels, size = canvas.tobytes(), canvas.size
    canvas.close()
    return pixels, size
