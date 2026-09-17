from pathlib import Path

from PIL import Image, ImageDraw, ImageFile

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.labeling.base import header_gap


def sample(path):
    image = Image.new('RGBA', (270, 300))
    draw = ImageDraw.Draw(image)
    draw.rectangle((160, 0, 269, 44), fill='white')
    draw.text((170, 10), 'LABEL', fill='black')
    draw.rectangle((30, 53, 239, 279), fill=(10, 20, 30, 180))
    image.save(path, dpi=(25.4, 25.4))
    image.close()
    return path


def test_virtual_gap_preview_decodes_each_source_once_for_all_measurements(tmp_path, monkeypatch):
    monkeypatch.setattr(header_gap, 'cache_root', lambda: tmp_path/'cache')
    paths = [sample(tmp_path/f'B{i}-1-T-Black-M-NO1-1.png') for i in range(4)]
    settings = LayoutSettings(
        dpi=25.4, media_width_mm=600, membrane_gap_mm=40,
        platform_name='Haloo', allow_rotation=True, number_images=True,
        color_block_enabled=True, cutter_mode='dual', preserve_header_gap=True,
        platform_reuse_qr=True, worker_threads=4,
    )
    original, decoded = ImageFile.ImageFile.load, []

    def counted(image, *args, **kwargs):
        name = Path(getattr(image, 'filename', ''))
        if image.fp is not None and name in paths:
            decoded.append(name)
        return original(image, *args, **kwargs)

    monkeypatch.setattr(ImageFile.ImageFile, 'load', counted)
    result = generate_layout(paths, tmp_path/'preview', settings, preview_only=True)

    assert len(result['placements']) == len(paths)
    assert sorted(decoded) == sorted(paths)
