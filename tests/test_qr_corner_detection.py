from PIL import Image
import pytest

from automatic_print.layout_engine.labeling.base.header_region import search_header
from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
from automatic_print.layout_engine.labeling.markers.qr_detection import detect_qr_location
from automatic_print.layout_engine.labeling.platform.membrane_region import detect_membrane_region
from automatic_print.layout_engine.measurement.measurement_session import measurement_session


@pytest.mark.parametrize('side', ['left', 'right'])
def test_plain_label_without_any_qr_is_found_in_preferred_region(tmp_path, side, monkeypatch):
    cv2 = pytest.importorskip('cv2')
    def forbidden(*args, **kwargs):
        raise AssertionError('No QR structure detector may run')
    monkeypatch.setattr(cv2, 'QRCodeDetector', forbidden)
    source = Image.new('RGBA', (1000, 1400))
    x = 20 if side == 'left' else 680
    source.paste('white', (x, 10, x+300, 140))
    source.paste('red', (x+30, 30, x+200, 60))
    source.paste('blue', (100, 600, 900, 1400))
    path = tmp_path/f'{side}.png'
    source.save(path)
    region = search_header(path)
    assert region.left == pytest.approx(x/1000)
    assert region.right == pytest.approx((x+300)/1000)
    assert region.top == pytest.approx(10/1400)
    assert region.bottom == pytest.approx(140/1400)
    assert detect_guide_band(path) == detect_membrane_region(path) == region
    center = detect_qr_location(path)
    assert center.x_ratio == pytest.approx((region.left+region.right)/2)


def test_does_not_search_lower_artwork_or_treat_transparency_as_paper(tmp_path):
    for name, fill in [('transparent', (255, 255, 255, 0)), ('faint', (255, 255, 255, 50))]:
        source = Image.new('RGBA', (1000, 1400), fill)
        source.paste('white', (450, 1200, 550, 1300))
        path = tmp_path/f'{name}.png'
        source.save(path)
        assert search_header(path) is None


def test_short_header_is_not_clipped_at_75_percent_height(tmp_path):
    source = Image.new('RGBA', (400, 100))
    source.paste('white', (10, 5, 200, 95))
    source.paste('black', (40, 20, 80, 70))
    path = tmp_path/'short.png'
    source.save(path)
    region = search_header(path)
    assert region.bottom == .95


def test_adjacent_paper_sections_join_without_inspecting_their_contents(tmp_path):
    source = Image.new('RGBA', (1000, 1400))
    source.paste('white', (20, 0, 250, 130))
    source.paste('white', (255, 0, 380, 130))
    path = tmp_path/'joined.png'
    source.save(path)
    region = search_header(path)
    assert region.left == .02 and region.right == .38


def test_stacked_corner_card_sections_split_by_printed_rule_are_rejoined(tmp_path):
    source = Image.new('RGBA', (1000, 1400))
    source.paste('white', (680, 0, 1000, 150))
    source.paste('black', (680, 30, 1000, 32))
    source.paste('blue', (100, 158, 900, 1400))
    path = tmp_path/'putian-card.png'
    source.save(path)

    region = search_header(path)

    assert region.left == pytest.approx(.68)
    assert region.right == pytest.approx(1)
    assert region.top == pytest.approx(0)
    assert region.bottom == pytest.approx(150/1400)


def test_tall_corner_card_is_rejoined_in_a_short_narrow_header_strip(tmp_path):
    source = Image.new('RGBA', (800, 1500))
    source.paste('white', (430, 0, 800, 30))
    source.paste('white', (195, 32, 800, 295))
    path = tmp_path/'narrow-putian-card.png'
    source.save(path)

    region = search_header(path)

    assert region is not None
    assert region.top == pytest.approx(0.0, abs=0.01)
    assert region.bottom == pytest.approx(295/1500, abs=0.01)


def test_component_fallback_matches_native_geometry():
    import numpy as np
    from automatic_print.layout_engine.labeling.base.header_region import _components
    mask = np.zeros((80, 120), dtype=bool)
    mask[5:60, 10:100] = True
    mask[20:35, 20:80] = False
    boxes = _components(mask)
    assert boxes == [[10, 5, 100, 60, int(mask.sum())]]


def test_header_region_survives_memory_cache_reset(tmp_path, monkeypatch):
    from automatic_print.layout_engine.labeling.base import header_region
    from automatic_print.layout_engine.measurement import measurement_cache
    monkeypatch.setattr(measurement_cache, 'cache_directory', lambda: tmp_path/'cache')
    source = Image.new('RGBA', (1000, 1400))
    source.paste('white', (680, 0, 1000, 150))
    path = tmp_path/'persistent-card.png'
    source.save(path)

    with measurement_session():
        expected = search_header(path)
    header_region._cached.cache_clear()
    monkeypatch.setattr(
        header_region, '_header_pixels',
        lambda _path: pytest.fail('persistent label geometry was not reused'),
    )
    with measurement_session():
        assert search_header(path) == expected
