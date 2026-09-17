import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.labeling.base import header_gap
from automatic_print.layout_engine.labeling.platform.membrane_region import MembraneRegion


def sample(path, gap=8, side='right'):
    image = Image.new('RGBA', (270, 300))
    draw = ImageDraw.Draw(image)
    x = 160 if side == 'right' else 0
    draw.rectangle((x, 0, x+109, 44), fill='white')
    draw.text((x+10, 10), 'LABEL', fill='black')
    draw.rectangle((30, 45+gap, 239, 279), fill=(10, 20, 30, 180))
    image.save(path, dpi=(25.4, 25.4))
    image.close()
    return path


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(header_gap, 'cache_root', lambda: tmp_path/'cache')


@pytest.mark.parametrize('side', ['left', 'right'])
def test_source_gap_copy_is_lossless_and_cached(tmp_path, side, monkeypatch):
    path = sample(tmp_path/'B1-1-T-Black-M-NO1-1.png', side=side)
    original_bytes = path.read_bytes()
    settings = LayoutSettings(dpi=25.4, membrane_gap_mm=40,
        manual_rotations=((str(path.resolve()), 90),))
    paths, adjusted, records = header_gap.prepare_paths([path], settings)
    assert paths[0] != path
    assert paths[0].name == path.name
    assert adjusted.manual_rotations[0][0] == str(paths[0].resolve())
    record = records[0]
    assert record['added_px'] == 32
    assert record['preparation_engine'] in {'libvips流式补距', 'Pillow兼容补距'}
    with Image.open(path) as source, Image.open(paths[0]) as prepared:
        split, added = record['split_px'], record['added_px']
        assert prepared.height == source.height+added
        assert prepared.info['dpi'] == source.info['dpi']
        assert np.array_equal(np.asarray(source)[:split], np.asarray(prepared)[:split])
        assert np.array_equal(np.asarray(source)[split:], np.asarray(prepared)[split+added:])
        assert prepared.crop((0, 45, 270, 85)).getchannel('A').getextrema()[1] == 0
    assert path.read_bytes() == original_bytes
    monkeypatch.setattr(header_gap, 'search_header', lambda _: pytest.fail('cache must avoid measurement'))
    assert header_gap.prepare_paths([path], settings)[0] == paths
    assert header_gap.prepare_paths(paths, adjusted)[0] == paths


def test_existing_gap_not_shrunk_and_unknown_retained(tmp_path):
    path = sample(tmp_path/'B1-1-T-Black-M-NO1-1.png', gap=60)
    paths, _, records = header_gap.prepare_paths([path], LayoutSettings(membrane_gap_mm=40))
    assert paths == [path]
    assert records[0]['added_px'] == 0
    unknown = tmp_path/'unknown.png'
    Image.new('RGBA', (100, 200), 'blue').save(unknown, dpi=(25.4, 25.4))
    paths, _, records = header_gap.prepare_paths([unknown], LayoutSettings(membrane_gap_mm=40))
    assert paths == [unknown]
    assert records[0]['warning']


def test_coloured_haloo_card_footer_is_included_before_gap(tmp_path):
    image = Image.new('RGBA', (1000, 700))
    draw = ImageDraw.Draw(image)
    draw.rectangle((600, 0, 999, 99), fill='white')
    draw.rectangle((600, 100, 999, 149), fill=(20, 80, 160, 255))
    draw.rectangle((100, 160, 899, 699), fill=(10, 20, 30, 255))

    split, added = header_gap.gap_geometry(
        image,
        MembraneRegion(.6, 0, 1, 100 / 700),
        200,
    )

    assert split == 150
    assert added == 190


def test_gap_summary_shows_total_changed_existing_and_failed_counts():
    records = [
        {'minimum_mm': 40, 'added_px': 226, 'added_mm': 31.89, 'warning': ''},
        {'minimum_mm': 40, 'added_px': 227, 'added_mm': 32.04, 'warning': ''},
        {'minimum_mm': 40, 'added_px': 0, 'warning': ''},
        {'minimum_mm': 40, 'added_px': 0, 'warning': '未找到可靠分界'},
    ]

    text = header_gap.gap_summary(records)

    for expected in ('目标 40 毫米', '共 4 张', '实际扩充 2 张',
                     '原本已满足 1 张', '未能扩充 1 张',
                     '31.89–32.04 毫米'):
        assert expected in text


def test_cache_expiry_parameter_change_and_original_freshness(tmp_path, monkeypatch):
    path = sample(tmp_path/'B1-1-T-Black-M-NO1-1.png')
    settings = LayoutSettings(dpi=25.4, membrane_gap_mm=40)
    prepared, _, records = header_gap.prepare_paths([path], settings)
    info = prepared[0].with_suffix('.json')
    os.utime(info, (1, 1))
    calls = []
    original = header_gap.search_header
    monkeypatch.setattr(header_gap, 'search_header', lambda p: (calls.append(p), original(p))[1])
    header_gap.prepare_paths([path], settings)
    assert calls == [path]
    wider, _, _ = header_gap.prepare_paths([path], replace(settings, membrane_gap_mm=50))
    assert wider != prepared
    sample(path, gap=10)
    with pytest.raises(ValueError, match='源文件发生变化'):
        header_gap.verify_records(records)


def test_missing_cache_sidecar_keeps_prepared_image_and_reports_warning(tmp_path):
    prepared = header_gap.cache_root()/'orphan'/'prepared.png'
    prepared.parent.mkdir(parents=True)
    Image.new('RGBA', (20, 20), 'blue').save(prepared)

    actual, record = header_gap.prepare_one(
        prepared, LayoutSettings(membrane_gap_mm=40),
    )

    assert actual == prepared
    assert record['added_px'] == 0
    assert '缓存记录损坏或缺失' in record['warning']


def test_stale_prepared_copy_is_regenerated_from_recorded_source(tmp_path):
    source = sample(tmp_path/'B1-1-T-Black-M-NO1-1.png')
    settings = LayoutSettings(dpi=25.4, membrane_gap_mm=40)
    prepared, _, _ = header_gap.prepare_paths([source], settings)
    prepared = prepared[0]
    prepared.with_suffix('.json').write_text(
        '{"source": "' + str(source) + '", "source_identity": ["missing", 0, 0]}',
        encoding='utf-8',
    )

    actual, record = header_gap.prepare_one(prepared, settings)

    assert actual.is_file()
    assert record['source'] == str(source)
    assert record['added_px'] == 32


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('degrees', [0, 90])
def test_output_and_preview_use_expanded_source_pixels(tmp_path, engine, degrees):
    path = sample(tmp_path/'B1-1-T-Black-M-NO1-1.png')
    settings = LayoutSettings(dpi=25.4, media_width_mm=600, membrane_gap_mm=40,
        allow_rotation=False, number_images=False, color_block_enabled=False,
        manual_rotations=((str(path.resolve()), degrees),), png_engine=engine)
    payloads = []
    result = generate_layout([path], tmp_path/'out', settings, plan_ready=payloads.append)
    assert result['header_gap'][0]['added_px'] == 32
    prepared = payloads[0]['planned'][0][0]
    p = result['placements'][0]
    with Image.open(tmp_path/'out'/result['filename']) as output, Image.open(prepared) as source:
        with source.rotate(degrees, expand=True) as rotated:
            actual = output.crop((p['x_px'], p['y_px'], p['x_px']+p['width_px'], p['y_px']+p['height_px']))
            expected = np.asarray(rotated)
            assert actual.size == rotated.size
            # Fully opaque originals must be exact; premultiplied half-alpha RGB
            # can differ by one in the native engine, but alpha must be unchanged.
            pixels = np.asarray(actual)
            assert np.array_equal(pixels[:,:,3], expected[:,:,3])
            assert np.array_equal(pixels[expected[:,:,3] == 255], expected[expected[:,:,3] == 255])
            assert np.abs(pixels.astype(int)-expected.astype(int)).max() <= 1
    preview = generate_layout([path], tmp_path/'preview', settings, preview_only=True)
    assert (preview['width_px'], preview['height_px']) == (result['width_px'], result['height_px'])
    assert not (tmp_path/'preview').exists()


def test_setting_default_and_persistence(tmp_path):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from automatic_print.ui.header_gap import build_header_gap
    from types import SimpleNamespace
    app = QApplication.instance() or QApplication([])
    prefs = QSettings(str(tmp_path/'prefs.ini'), QSettings.IniFormat)
    window = SimpleNamespace(preferences=prefs)
    field = build_header_gap(window)
    assert field.value() == 40
    field.setValue(35)
    assert build_header_gap(window).value() == 35
    assert app


@pytest.mark.parametrize('mode', ['single', 'dual'])
@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
def test_complete_double_orders_segmented_with_safe_corridors(tmp_path, mode, engine):
    paths = [sample(tmp_path/f'B{order}-1-T-Black-M-NO1-{face}.png', side='left' if order % 2 else 'right')
             for order in range(4) for face in (1, 2)]
    settings = LayoutSettings(dpi=25.4, membrane_gap_mm=40, cutter_mode=mode,
        cutter_auto_knife=True, cutter_single_row_rotation=True, cutter_compare_whole_rotation=True,
        cutter_left_marker_external=True, preserve_header_gap=True, cutter_knife_dots=False,
        png_engine=engine, output_parts=3, save_memory_unlimited=True)
    result = generate_layout(paths, tmp_path/'out', settings)
    assert result['order_check']['orders'] == 4
    assert result['order_check']['double_pairs'] == 4
    for part in result['parts']:
        assert len(part['placements']) % 2 == 0
        with Image.open(tmp_path/'out'/part['filename']) as output:
            for p in part['placements']:
                original = next(path for path in paths if path.name == p['source'])
                prepared = header_gap.prepare_one(original, settings)[0]
                with Image.open(prepared) as source, source.rotate(p['rotation_degrees'], expand=True) as rotated:
                    crop = output.crop((p['x_px'], p['y_px'], p['x_px']+rotated.width, p['y_px']+rotated.height))
                    expected = np.asarray(rotated)
                    actual = np.asarray(crop)
                    # Added labels may occupy verified transparent header-card
                    # pixels, but original printed pixels must remain exact.
                    opaque = expected[:, :, 3] == 255
                    assert np.array_equal(actual[opaque], expected[opaque])
            if mode == 'dual':
                for zone in part['cut_corridor'].get('zones', [part['cut_corridor']]):
                    assert output.crop((zone['safe_left_px'], zone.get('start_y_px', 0),
                        zone['safe_right_px'], zone.get('end_y_px', output.height))).getchannel('A').getextrema()[1] == 0
