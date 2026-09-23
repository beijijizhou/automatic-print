"""Four inspection examples using the same per-image geometry as production."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from ....layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
from ....layout_engine.intake.preparation.item_factory import read_items
from ....layout_engine.measurement.measurement_session import measurement_session
from ....runtime.resources import asset_path
from .render import render_direction_diagram, render_example

CASES = (("left", 0), ("right", 0), ("left", 90), ("right", 90))


def diagram_source(path, side):
    """Last-resort code diagram if the packaged sample is unavailable."""
    image = Image.new('RGBA', (820, 360))
    draw = ImageDraw.Draw(image)
    x = 280 if side == 'left' else 590
    # Header detection deliberately finds an opaque light card, while label
    # placement accepts both light paper and transparency as unused space.  A
    # transparent outline is mistaken for the small white holes in the QR
    # symbol and collapses the detected band to only a few pixels.  Keep a
    # realistically sized light card so every ordinary label setting can use
    # the same production geometry without reading an old batch.
    draw.rectangle((x, 0, x+229, 119), fill='white', outline='black', width=1)
    draw.text((x+4, 7), 'M / NO1', fill='black')
    draw.text((x+4, 23), 'LABEL', fill='black')
    for dx, dy in ((0, 0), (28, 0), (0, 28)):
        draw.rectangle((x+168+dx, 8+dy, x+189+dx, 29+dy), fill='black')
        draw.rectangle((x+173+dx, 13+dy, x+184+dx, 24+dy), fill='white')
    # Leave the same clear strip below the card that a production image needs.
    # After a 90-degree rotation this strip becomes the horizontal home for the
    # batch label, so artwork must not intrude into it.
    draw.ellipse((95, 190, 325, 350), fill='#135e86')
    draw.polygon(((115, 330), (210, 210), (305, 330)), fill='#efbf44')
    image.save(path, dpi=(25.4, 25.4))
    image.close()


def fallback_source(path, side):
    """Use one bundled, anonymized Haloo image for both card orientations."""
    with Image.open(asset_path('haloo-preview-sample.png')) as source:
        if side == 'left':
            mirrored = source.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            image = Image.new('RGBA', (1200, source.height))
            image.alpha_composite(mirrored, (360, 0))
            mirrored.close()
        else:
            image = source.copy()
        dpi = source.info.get('dpi', (25.4, 25.4))
    try:
        image.save(path, dpi=dpi)
    finally:
        image.close()


def _render_case(path, settings, side, degrees, production):
    from ....layout_engine.labeling.base.header_gap import prepare_paths
    from ....layout_engine.intake.metadata.output_dpi import resolve_output_dpi
    from ....layout_engine.labeling.markers.left_marker import external_left_item

    original = path
    config = settings if production else replace(
        settings, label_batch_name='示意批次', label_sequence_total=1,
    )
    prepared, config, _ = prepare_paths([path], config)
    path = prepared[0]
    config = replace(config, allow_rotation=False,
        manual_rotations=((str(path.resolve()), degrees),),
        sequence_numbers=((str(path.resolve()), 1),))
    config = resolve_output_dpi([path], config)
    choices, labels = read_items([path], config, None)
    item = choices[0][0]
    if config.cutter_mode in {'single', 'dual'}:
        item = external_left_item(item)
    region = detect_guide_band(path)
    if region is None:
        raise ValueError(f'{original.name}：无法定位膜标签卡片')
    region = region.rotated(degrees)
    pixels, size, focus_pixels, focus_size = render_example(
        path, item, labels, config, region)
    return {'side': side, 'degrees': degrees, 'production': production,
        'dpi': config.dpi, 'mode': config.cutter_mode,
        'source': str(original) if production else '', 'item': item,
        'region': region, 'pixels': pixels, 'size': size,
        'focus_pixels': focus_pixels, 'focus_size': focus_size,
        'label_text': labels.get(item.index, ''),
        'detail': f'刀码：左基准，距图顶 {(item.block_ry-item.image_ry)*25.4/config.dpi:.1f}毫米'
                  f' · 图外间隙 {(item.image_rx-item.block_rx-item.block_width)*25.4/config.dpi:.1f}毫米'
                  f' · 标签距图顶 {(item.label_ry-item.image_ry)*25.4/config.dpi:.1f}毫米'}


def build_examples(paths, settings):
    # No folder traversal/startup restore. Only explicit current-batch paths.
    with measurement_session(), TemporaryDirectory(prefix='ha-marker-preview-') as directory:
        candidates = {'left': [], 'right': []}
        unreadable = []
        for raw in paths[:24]:
            path = Path(raw)
            try:
                region = detect_guide_band(path)
            except Exception:  # Decoder backends (including libvips) have distinct error types.
                region = None
            if region is None:
                unreadable.append(path.name)
                continue
            side = 'left' if (region.left+region.right)/2 < .5 else 'right'
            candidates[side].append(path)
        fallback = {}
        for side in candidates:
            fallback[side] = []
            haloo = Path(directory)/f'HALOO-DEMO-{side}-M-NO1-1.png'
            try:
                fallback_source(haloo, side)
                fallback[side].append((haloo, 'haloo'))
            except (OSError, ValueError):
                pass
            code = Path(directory)/f'CODE-DEMO-{side}-M-NO1-1.png'
            diagram_source(code, side)
            fallback[side].append((code, 'code'))
        results = []
        for side, degrees in CASES:
            failures = []
            choices = [(path, 'production') for path in candidates[side]] + fallback[side]
            for path, kind in choices:
                production = kind == 'production'
                try:
                    row = _render_case(path, settings, side, degrees, production)
                except Exception as error:  # A single corrupt candidate never blanks all cases.
                    failures.append(f'{path.name}：{error}')
                    continue
                row['sample_kind'] = kind
                row['fallback_reason'] = ('；'.join(failures[:2]) if failures else
                    f'抽样图片无法识别膜标签：{unreadable[0]}' if unreadable and not production else '')
                results.append(row)
                break
            else:
                # An illustration is still useful when strict production
                # placement cannot prove a safe badge rectangle. Never invent
                # printable coordinates to make the preview look successful.
                path, kind = fallback[side][0]
                pixels, size = render_direction_diagram(path, degrees)
                results.append({'side': side, 'degrees': degrees,
                    'production': False, 'sample_kind': f'{kind}-direction',
                    'fallback_reason': ((f'抽样图片无法识别膜标签：{unreadable[0]}；'
                        if unreadable else '') + '；'.join(failures[:2])),
                    'dpi': settings.dpi, 'mode': settings.cutter_mode,
                    'source': '', 'item': None, 'region': detect_guide_band(path).rotated(degrees),
                    'pixels': pixels, 'size': size,
                    'focus_pixels': pixels, 'focus_size': size,
                    'detail': '当前参数未验证出安全的文字位置；仅展示方向，不代表可生产坐标。'})
        return results
