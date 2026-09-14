"""Bounded preview pixels, with production geometry and production badge rendering."""
from PIL import Image, ImageDraw
from ..layout_engine.dynamic_label import source_label_badge
from ..layout_engine.platform_label import platform_badge


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
        badge = platform_badge(settings.platform_name, item.platform_height)
        paste(badge, item.platform_rx, item.platform_ry, item.platform_width, item.platform_height)
        badge.close()
    if item.block_width:
        x, y = item.block_rx*scale, item.block_ry*scale
        draw.rectangle((round(x), round(y), round((item.block_rx+item.block_width)*scale)-1,
                        round((item.block_ry+item.block_height)*scale)-1), fill=settings.color_block_color)
    pixels = canvas.tobytes()
    canvas.close()
    return pixels, (width, height)
