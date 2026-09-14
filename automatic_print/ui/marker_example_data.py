"""Four inspection examples using the same per-image geometry as production."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from ..layout_engine.cut_guide_geometry import detect_guide_band
from ..layout_engine.item_factory import read_items
from ..layout_engine.measurement_session import measurement_session
from .marker_example_render import render_example

CASES = (("left", 0), ("right", 0), ("left", 90), ("right", 90))


def diagram_source(path, side):
    """Fallback is explicitly a diagram, never a claimed production photograph."""
    image = Image.new('RGBA', (270, 300))
    draw = ImageDraw.Draw(image)
    x = 0 if side == 'left' else 160
    draw.rectangle((x, 0, x+109, 44), fill='white')
    draw.text((x+4, 7), 'M / NO1', fill='black')
    draw.text((x+4, 23), 'LABEL', fill='black')
    for dx, dy in ((0, 0), (18, 0), (0, 18)):
        draw.rectangle((x+70+dx, 5+dy, x+83+dx, 18+dy), fill='black')
        draw.rectangle((x+73+dx, 8+dy, x+80+dx, 15+dy), fill='white')
    draw.ellipse((45, 90, 225, 265), fill='#135e86')
    draw.polygon(((60, 220), (135, 105), (210, 220)), fill='#efbf44')
    image.save(path, dpi=(25.4, 25.4))
    image.close()


def build_examples(paths, settings):
    samples = {}
    # No folder traversal/startup restore. Only explicit current-batch paths.
    with measurement_session(), TemporaryDirectory(prefix='ha-marker-preview-') as directory:
        for path in paths[:24]:
            region = detect_guide_band(path)
            if region:
                side = 'left' if (region.left+region.right)/2 < .5 else 'right'
                samples.setdefault(side, Path(path))
            if len(samples) == 2:
                break
        fallback = {}
        for side in ('left', 'right'):
            path = Path(directory)/f'B-{side}-M-NO1-1.png'
            diagram_source(path, side)
            fallback[side] = path
        results = []
        for side, degrees in CASES:
            path = samples.get(side, fallback[side])
            config = replace(settings, allow_rotation=False, cutter_mode='dual',
                cutter_left_marker_external=True,
                color_block_position='left_top', color_block_offset_y_mm=0,
                manual_rotations=((str(path.resolve()), degrees),),
                sequence_numbers=((str(path.resolve()), 1),))
            choices, labels = read_items([path], config, None)
            item = choices[0][0]
            from ..layout_engine.left_marker import external_left_item
            item = external_left_item(item)
            pixels, size = render_example(path, item, labels, config)
            region = detect_guide_band(path).rotated(degrees)
            results.append({'side': side, 'degrees': degrees, 'production': side in samples,
                'source': str(path) if side in samples else '', 'item': item,
                'region': region, 'pixels': pixels, 'size': size,
                'detail': f'刀码：左基准，距图顶 {(item.block_ry-item.image_ry)*25.4/config.dpi:.1f}毫米'
                          f' · 图外间隙 {(item.image_rx-item.block_rx-item.block_width)*25.4/config.dpi:.1f}毫米'
                          f' · 标签距图顶 {(item.label_ry-item.image_ry)*25.4/config.dpi:.1f}毫米'})
        return results
