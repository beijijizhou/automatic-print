from dataclasses import replace
from pathlib import Path
import pytest
from PIL import Image
import pyvips
from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.png_codecs.streaming import validate_final_canvas, validate_header
from automatic_print.layout_engine.vips_renderer import _balanced_vertical_join


def test_final_canvas_rejects_actual_pixel_in_corridor():
    image = pyvips.Image.black(100, 200, bands=4)
    check = {'safe_left_px': 45, 'safe_right_px': 55}
    validate_final_canvas(image, check, [], [])
    assert check['pixel_verified']
    occupied = image.insert(pyvips.Image.black(1, 1, bands=4).new_from_image(
        [1, 2, 3, 255]), 50, 199)
    with pytest.raises(ValueError, match='禁止输出'):
        validate_final_canvas(occupied, check, [], [])


def test_header_checks_dimensions_crc_and_complete_file(tmp_path):
    for name, corrupt in [('size', False), ('crc', True), ('tail', True)]:
        path = tmp_path/(name+'.png')
        Image.new('RGBA', (100,200)).save(path)
        if corrupt:
            with path.open('r+b') as file:
                file.seek(29 if name=='crc' else -1, 0 if name=='crc' else 2)
                file.write(b'\x00')
        with pytest.raises(ValueError, match='禁止打印'):
            validate_header(path, 101 if name=='size' else 100, 200)
        assert path.with_suffix('.禁止打印').exists()


def test_streaming_never_reopens_png_for_pixel_decode(tmp_path, monkeypatch):
    from automatic_print.layout_engine import service
    def forbidden(*a, **k):
        raise AssertionError('must not decode saved PNG')
    monkeypatch.setattr(service, 'validate_vips_output', forbidden)
    path = tmp_path/'B1-1-T-Black-M-NO1-1.png'
    with Image.new('RGBA', (100,200)) as image:
        image.paste('blue',(0,50,100,200))
        image.save(path,dpi=(25.4,25.4))
    phases = []
    settings = LayoutSettings(dpi=25.4,media_width_mm=500,cutter_mode='dual',
        cutter_auto_knife=True,png_engine='libvips',png_streaming=True)
    result = generate_layout([path],tmp_path/'out',settings,phase_ready=phases.append)
    assert '输出文件安全复核' not in phases
    assert '最终画布刀位检查' in phases
    assert '原生分块流式PNG' in result['png_save_details']['encoder']
    assert result['cut_corridor']['pixel_verified']


def test_streaming_uses_fixed_fast_png_filter(tmp_path):
    from automatic_print.layout_engine.atomic_png import save_png
    class Canvas:
        width, height = 10, 20
        options = None
        def pngsave(self, path, **options):
            self.options = options
            Path(path).write_bytes(b'complete')
    canvas = Canvas()
    target = tmp_path/'filter.png'
    settings = LayoutSettings(png_streaming=True, png_compression_level=1)
    details = save_png(canvas, target, settings, True, None)
    assert canvas.options['filter'] == 'up'
    assert '固定UP滤波' in details['steps'][0]['name']


def test_balanced_vertical_join_preserves_every_row_and_gap():
    rows = [
        pyvips.Image.black(7, height, bands=4).new_from_image(color)
        for height, color in ((2, [1, 2, 3, 255]), (3, [4, 5, 6, 255]),
                              (1, [7, 8, 9, 255]), (4, [10, 11, 12, 255]))
    ]
    joined = _balanced_vertical_join(rows)
    pixels = bytes(joined.write_to_memory())
    expected = b''.join(bytes(color)*7*height for height, color in (
        (2, [1, 2, 3, 255]), (3, [4, 5, 6, 255]),
        (1, [7, 8, 9, 255]), (4, [10, 11, 12, 255])))
    assert (joined.width, joined.height) == (7, 10)
    assert pixels == expected
