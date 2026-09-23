"""Bounded preview pixels, with production geometry and production badge rendering."""
from PIL import Image, ImageDraw
from ....layout_engine.labeling.base.labels import label_badge
from ....layout_engine.labeling.base.dynamic_label import source_label_badge
from ....layout_engine.labeling.platform.platform_label import placement_badge, platform_text


def render_example(path, item, labels, settings, region):
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

    focus_pixels, focus_size = b'', (0, 0)
    with Image.open(path) as source:
        with source.convert('RGBA') as rgba:
            with rgba.rotate(item.rotation_degrees, expand=True) as rotated:
                paste(rotated, item.image_rx, item.image_ry, item.width, item.height)
                if item.label_width:
                    badge = source_label_badge(
                        labels[item.index], settings, path, item.rotation_degrees)
                    try:
                        focus_pixels, focus_size = _focus_preview(
                            rotated, item, labels[item.index], settings, region)
                        paste(badge, item.label_rx, item.label_ry,
                              item.label_width, item.label_height)
                    finally:
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
    return pixels, (width, height), focus_pixels, focus_size


def _focus_preview(source, item, text, settings, region):
    """Keep all three production coordinates and add one connected text loupe."""
    label = (item.label_rx, item.label_ry,
             item.label_rx+item.label_width, item.label_ry+item.label_height)
    card = (item.image_rx+region.left*item.width,
            item.image_ry+region.top*item.height,
            item.image_rx+region.right*item.width,
            item.image_ry+region.bottom*item.height)
    block = (item.block_rx, item.block_ry,
             item.block_rx+item.block_width, item.block_ry+item.block_height)
    areas = [label, card] + ([block] if item.block_width and item.block_height else [])
    padding = max(12, item.label_height*.7)
    left = min(area[0] for area in areas)-padding
    top = min(area[1] for area in areas)-padding
    right = max(area[2] for area in areas)+padding
    bottom = max(area[3] for area in areas)+padding
    width, height = max(1, right-left), max(1, bottom-top)
    scale = max(.01, min(2000/width, 420/height))
    main = Image.new('RGBA', (
        max(1, round(width*scale)), max(1, round(height*scale))), 'white')
    try:
        source_area = (
            max(left, item.image_rx), max(top, item.image_ry),
            min(right, item.image_rx+item.width),
            min(bottom, item.image_ry+item.height),
        )
        if source_area[2] > source_area[0] and source_area[3] > source_area[1]:
            source_x, source_y = source.width/item.width, source.height/item.height
            source_box = (
                round((source_area[0]-item.image_rx)*source_x),
                round((source_area[1]-item.image_ry)*source_y),
                round((source_area[2]-item.image_rx)*source_x),
                round((source_area[3]-item.image_ry)*source_y),
            )
            shown_size = (
                max(1, round((source_area[2]-source_area[0])*scale)),
                max(1, round((source_area[3]-source_area[1])*scale)),
            )
            with source.crop(source_box) as crop:
                shown_source = crop.resize(shown_size, Image.Resampling.LANCZOS)
            main.alpha_composite(shown_source, (
                round((source_area[0]-left)*scale),
                round((source_area[1]-top)*scale)))
            shown_source.close()

        label_size = (max(1, round(item.label_width*scale)),
                      max(1, round(item.label_height*scale)))
        badge = _preview_badge(text, settings, scale, label_size)
        try:
            label_x = round((item.label_rx-left)*scale)
            label_y = round((item.label_ry-top)*scale)
            main.alpha_composite(badge, (label_x, label_y))
        finally:
            badge.close()
        draw = ImageDraw.Draw(main)
        stroke = max(3, round(scale))
        draw.rectangle(_scaled_box(card, left, top, scale),
                       outline='#d97706', width=stroke)
        draw.rectangle(_scaled_box(label, left, top, scale),
                       outline='#a21caf', width=stroke)
        if item.block_width and item.block_height:
            draw.rectangle(_scaled_box(block, left, top, scale),
                           fill=settings.color_block_color,
                           outline='#dc2626', width=stroke)

        canvas_width = max(1100, main.width)
        canvas = Image.new('RGBA', (canvas_width, main.height+240), 'white')
        offset_x = (canvas_width-main.width)//2
        canvas.alpha_composite(main, (offset_x, 0))
        loupe_size = (min(canvas_width-100, 1200), 180)
        loupe = _preview_badge(text, settings,
                               max(1, 150/max(1, item.label_height)), loupe_size)
        try:
            loupe_x = (canvas_width-loupe.width)//2
            loupe_y = main.height+40
            canvas.alpha_composite(loupe, (loupe_x, loupe_y))
            canvas_draw = ImageDraw.Draw(canvas)
            canvas_draw.rectangle((loupe_x-6, loupe_y-6,
                                   loupe_x+loupe.width+5, loupe_y+loupe.height+5),
                                  outline='#a21caf', width=6)
            label_center_x = offset_x+round(((label[0]+label[2])/2-left)*scale)
            label_bottom_y = round((label[3]-top)*scale)
            canvas_draw.line((label_center_x, label_bottom_y,
                              canvas_width//2, loupe_y-6),
                             fill='#a21caf', width=5)
        finally:
            loupe.close()
        return canvas.tobytes(), canvas.size
    finally:
        main.close()
        if 'canvas' in locals():
            canvas.close()


def _preview_badge(text, settings, scale, size):
    dpi = max(settings.dpi, round(settings.dpi*scale))
    badge = label_badge(text, dpi, settings.number_font_size_mm, size[0])
    canvas = Image.new('RGBA', size)
    if badge.width > canvas.width or badge.height > canvas.height:
        badge.thumbnail(canvas.size, Image.Resampling.LANCZOS)
    canvas.alpha_composite(
        badge, ((canvas.width-badge.width)//2, (canvas.height-badge.height)//2))
    badge.close()
    return canvas


def _scaled_box(box, left, top, scale):
    return tuple(round((value-(left if index % 2 == 0 else top))*scale)
                 for index, value in enumerate(box))


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
