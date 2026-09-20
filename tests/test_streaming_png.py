from dataclasses import replace
from pathlib import Path
import pytest
from PIL import Image
import pyvips
from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.rendering.png.streaming import validate_final_canvas, validate_header, validate_chunks
from automatic_print.layout_engine.rendering.engines.vips_renderer import _balanced_vertical_join


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
        with pytest.raises(ValueError, match='生成未完成'):
            validate_header(path, 101 if name=='size' else 100, 200)
        assert path.with_suffix('.生成未完成').exists()


def test_streaming_checks_saved_png_once_without_pre_rendering_canvas(tmp_path):
    paths = [tmp_path/f'B{index}-1-T-Black-M-NO1-1.png' for index in (1, 2)]
    for path in paths:
        with Image.new('RGBA', (100,200)) as image:
            image.paste('blue',(0,50,100,200))
            image.save(path,dpi=(25.4,25.4))
    phases = []
    settings = LayoutSettings(dpi=25.4,media_width_mm=500,cutter_mode='dual',
        cutter_auto_knife=True,png_engine='libvips',png_streaming=True)
    result = generate_layout(paths,tmp_path/'out',settings,phase_ready=phases.append)
    assert '最终画布刀位检查' not in phases
    assert '输出文件安全复核' in phases
    assert '原生逐行流式PNG' in result['png_save_details']['encoder']
    assert result['timings_seconds']['output_validation'] >= 0
    assert any(row['name'] == '输出PNG数据块CRC、尺寸与格式复核'
               for row in result['png_save_details']['steps'])
    assert result['cut_corridor']['pixel_verified']


def test_chunk_validation_rejects_corrupted_saved_data(tmp_path):
    path = tmp_path/'source.png'
    Image.new('RGBA', (100, 200)).save(path, compress_level=1)
    validate_chunks(path, 100, 200)
    with path.open('r+b') as stream:
        stream.seek(50)
        value = stream.read(1)
        stream.seek(50)
        stream.write(bytes((value[0] ^ 1,)))
    with pytest.raises(ValueError, match='校验失败'):
        validate_chunks(path, 100, 200)


def test_row_encoder_rejects_final_alpha_inside_corridor(tmp_path):
    from automatic_print.layout_engine.rendering.png.row_stream import save
    image = pyvips.Image.black(100, 10, bands=4)
    occupied = pyvips.Image.black(1, 1, bands=4).new_from_image(
        [1, 2, 3, 255]
    )
    image = image.insert(occupied, 50, 9)
    check = {'safe_left_px': 45, 'safe_right_px': 55}
    with pytest.raises(ValueError, match='切割安全通道'):
        save([(0, 10, image)], tmp_path/'unsafe.png', 100, 10,
             LayoutSettings(dpi=25.4), [], [], None, check)


def test_prefetched_rows_match_serial_output_across_transparent_gap(tmp_path):
    from automatic_print.layout_engine.rendering.png.row_stream import save
    from hashlib import sha256

    red = pyvips.Image.black(20, 10, bands=4).new_from_image([255, 0, 0, 255])
    blue = pyvips.Image.black(20, 10, bands=4).new_from_image([0, 0, 255, 255])
    rows = [(0, 10, red), (30, 10, blue)]
    serial = tmp_path/'serial.png'
    parallel = tmp_path/'parallel.png'
    save(rows, serial, 20, 50, LayoutSettings(worker_threads=1), [], [], None)
    save(rows, parallel, 20, 50, LayoutSettings(worker_threads=2), [], [], None)

    assert sha256(serial.read_bytes()).digest() == sha256(parallel.read_bytes()).digest()
    with Image.open(parallel) as image:
        assert image.getpixel((0, 0)) == (255, 0, 0, 255)
        assert image.getpixel((0, 15)) == (0, 0, 0, 0)
        assert image.getpixel((0, 30)) == (0, 0, 255, 255)


def test_saved_png_reader_rejects_alpha_inside_corridor(tmp_path):
    from automatic_print.layout_engine.rendering.png.corridor_reader import validate
    path = tmp_path/'occupied.png'
    with Image.new('RGBA', (100, 200)) as image:
        image.putpixel((50, 199), (1, 2, 3, 255))
        image.save(path, compress_level=1)
    with pytest.raises(ValueError, match='滤波方式|切割安全通道'):
        validate(path, 100, 200, [{'safe_left_px': 45, 'safe_right_px': 55}])


def test_saved_png_reader_allows_declared_guide_pixels(tmp_path):
    from automatic_print.layout_engine.rendering.png.corridor_reader import validate
    from automatic_print.layout_engine.cutting.geometry.printed_guides import dot_sprite
    path = tmp_path/'guide.png'
    box = (49, 190, 3)
    with Image.new('RGBA', (100, 200)) as image, dot_sprite(3) as dot:
        image.alpha_composite(dot, box[:2])
        image.save(path, compress_level=1)
    validate(path, 100, 200, [{'safe_left_px': 45, 'safe_right_px': 55}], [box])


def test_streaming_uses_fixed_fast_png_filter(tmp_path):
    from automatic_print.layout_engine.rendering.storage.atomic_png import save_png
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
    assert details['encoder'] == '原生分块流式PNG'
    assert [step['name'] for step in details['steps']] == [
        '启动至首批PNG数据（含首段延迟合成）',
        'PNG持续生成、压缩与写入',
        '编码收尾与文件刷新',
        '未完成文件原子发布',
    ]
    assert '不虚构互斥CPU耗时' in details['timing_note']


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
