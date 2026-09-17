"""Four inspection examples using the same per-image geometry as production."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from ....layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
from ....layout_engine.intake.preparation.item_factory import read_items
from ....layout_engine.measurement.measurement_session import measurement_session
from .render import render_example

CASES = (("left", 0), ("right", 0), ("left", 90), ("right", 90))


def diagram_source(path, side):
    """Fallback is explicitly a diagram, never a claimed production photograph."""
    image = Image.new('RGBA', (420, 360))
    draw = ImageDraw.Draw(image)
    x = 0 if side == 'left' else 190
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
            production = side in samples
            path = samples.get(side, fallback[side])
            from ....layout_engine.labeling.base.header_gap import prepare_paths
            # A generated sample has no real batch folder.  Giving it the
            # temporary directory name produces a long, meaningless label and
            # can make the rotated diagram fail despite valid user settings.
            source_settings = settings if production else replace(
                settings, label_batch_name='示意批次', label_sequence_total=1,
            )
            prepared, example_settings, _ = prepare_paths([path], source_settings)
            path = prepared[0]
            config = replace(example_settings, allow_rotation=False,
                manual_rotations=((str(path.resolve()), degrees),),
                sequence_numbers=((str(path.resolve()), 1),))
            from ....layout_engine.intake.metadata.output_dpi import resolve_output_dpi
            config = resolve_output_dpi([path], config)
            choices, labels = read_items([path], config, None)
            item = choices[0][0]
            from ....layout_engine.labeling.markers.left_marker import external_left_item
            if config.cutter_mode in {'single', 'dual'}:
                item = external_left_item(item)
            pixels, size = render_example(path, item, labels, config)
            region = detect_guide_band(path).rotated(degrees)
            results.append({'side': side, 'degrees': degrees, 'production': production,
                'dpi': config.dpi, 'mode': config.cutter_mode,
                'source': str(path) if side in samples else '', 'item': item,
                'region': region, 'pixels': pixels, 'size': size,
                'detail': f'刀码：左基准，距图顶 {(item.block_ry-item.image_ry)*25.4/config.dpi:.1f}毫米'
                          f' · 图外间隙 {(item.image_rx-item.block_rx-item.block_width)*25.4/config.dpi:.1f}毫米'
                          f' · 标签距图顶 {(item.label_ry-item.image_ry)*25.4/config.dpi:.1f}毫米'})
        return results
