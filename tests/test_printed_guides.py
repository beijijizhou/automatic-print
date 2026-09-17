from PIL import Image
from types import SimpleNamespace
import pytest

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.cutting.geometry import printed_guides
from automatic_print.layout_engine.labeling.platform.membrane_region import MembraneRegion


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
def test_saved_png_contains_only_qr_band_dots(tmp_path, monkeypatch, engine):
    if engine == 'libvips':
        pytest.importorskip('pyvips')
    paths = []
    for i in range(4):
        path = tmp_path / f'B{i}-1-T-White-M-NO1-1.png'
        Image.new('RGBA', (180, 250), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    monkeypatch.setattr(printed_guides, 'detect_guide_band',
                        lambda path: MembraneRegion(.6, .04, .9, .2))
    settings = LayoutSettings(dpi=25.4, margin_mm=0, cutter_mode='dual',
                              number_images=False, png_engine=engine)
    result = generate_layout(paths, tmp_path/'out', settings)
    assert result['printed_guides']['span_count'] == 2
    assert result['cut_corridor']['pixel_verified']
    with Image.open(tmp_path/'out'/result['filename']) as image:
        red_y = [y for y in range(image.height) if image.getpixel((300, y))[3]]
        assert red_y
        rows = sorted(set(p['y_px'] for p in result['placements']))
        assert all(any(top+10 <= y < top+50 for top in rows) for y in red_y)
        assert all(image.getpixel((300, y)) == (255, 0, 0, 255) for y in red_y)
        assert len(red_y) < 80


def test_vips_allowlist_does_not_hide_artwork_or_extra_red_ink():
    pyvips = pytest.importorskip('pyvips')
    check = {'safe_left_px': 47, 'safe_right_px': 53}
    canvas = pyvips.Image.black(100, 100, bands=4).copy(interpretation='srgb')
    boxes = [(49, 10, 3), (49, 20, 3)]
    printed_guides.validate_vips_canvas(canvas, check)
    marked = printed_guides.paint_guides(canvas, boxes, True)
    assert printed_guides.vips_corridor_is_clear(marked, check, boxes)
    assert not printed_guides.vips_corridor_is_clear(marked, check)
    extra = marked.draw_rect([255, 0, 0, 255], 50, 60, 1, 1, fill=True)
    assert not printed_guides.vips_corridor_is_clear(extra, check, boxes)
    with pytest.raises(ValueError, match='禁止保存'):
        printed_guides.validate_vips_canvas(marked, check)


def test_vips_multi_zone_corridors_share_one_safe_scan():
    pyvips = pytest.importorskip('pyvips')
    blank = pyvips.Image.black(100, 100, bands=4).copy(interpretation='srgb')
    checks = [
        {'safe_left_px': 20, 'safe_right_px': 24,
         'start_y_px': 0, 'end_y_px': 60},
        {'safe_left_px': 70, 'safe_right_px': 74,
         'start_y_px': 60, 'end_y_px': 100},
    ]
    assert printed_guides.vips_corridors_are_clear(blank, checks)
    outside = blank.draw_rect([1, 2, 3, 255], 50, 50, 1, 1, fill=True)
    assert printed_guides.vips_corridors_are_clear(outside, checks)
    first_zone = outside.draw_rect([1, 2, 3, 255], 22, 20, 1, 1, fill=True)
    assert not printed_guides.vips_corridors_are_clear(first_zone, checks)
    second_zone = outside.draw_rect([1, 2, 3, 255], 72, 80, 1, 1, fill=True)
    assert not printed_guides.vips_corridors_are_clear(second_zone, checks)


def test_vips_corridor_scan_uses_bounded_height(monkeypatch):
    pyvips = pytest.importorskip('pyvips')
    blank = pyvips.Image.black(100, 10000, bands=4)
    heights = []
    original = printed_guides._vips_allowed_mask
    def observed(width, height, left, top, boxes, rectangles):
        heights.append(height)
        return original(width, height, left, top, boxes, rectangles)
    monkeypatch.setattr(printed_guides, '_vips_allowed_mask', observed)
    assert printed_guides.vips_corridors_are_clear(
        blank, [{'safe_left_px': 45, 'safe_right_px': 55}],
    )
    assert len(heights) == 3
    assert max(heights) <= printed_guides.CORRIDOR_SCAN_ROWS


def test_missing_qr_is_reported_without_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(printed_guides, 'detect_guide_band', lambda path: None)
    path = tmp_path/'missing.png'
    placement = SimpleNamespace(cut_zone='', y_px=0)
    spans, missing = printed_guides.collect_guides([(path, placement)], LayoutSettings(cutter_mode='dual'))
    assert spans == []
    assert missing == ['missing.png']
