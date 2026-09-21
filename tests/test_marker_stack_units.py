from pathlib import Path

from automatic_print.layout_engine import LayoutSettings
from automatic_print.layout_engine.labeling.markers.marker_stack import stacked_coordinates


def test_explicit_stack_font_does_not_search_membrane_card(monkeypatch):
    from automatic_print.layout_engine.labeling.platform import platform_label

    def unexpected_search(*args):
        raise AssertionError('外置明确字号无需搜索膜标签')

    monkeypatch.setattr(platform_label, 'detect_guide_band', unexpected_search)
    settings = LayoutSettings(dpi=25.4, platform_name='隆丰',
        platform_below_marker=True, platform_font_height_mm=6)
    x, y, width, height = platform_label.platform_geometry(
        Path('unused.png'), settings, 270, 300, 90,
    )
    assert (x, y, width) == (0, 0, 6)
    assert height > 0


def test_platform_badge_reuses_qr_card_when_header_is_preserved(monkeypatch):
    from automatic_print.layout_engine.labeling.platform import platform_label
    from automatic_print.layout_engine.labeling.platform.membrane_region import MembraneRegion
    region = MembraneRegion(.7, .05, .9, .2)
    monkeypatch.setattr(platform_label, 'detect_guide_band', lambda _path: region)
    monkeypatch.setattr(platform_label, 'card_space', lambda *_args: (42, 3))
    settings = LayoutSettings(
        dpi=25.4, platform_name='隆丰', platform_font_height_mm=6,
        platform_below_marker=True, platform_reuse_qr=True,
        preserve_header_gap=True,
    )
    x, y, width, height = platform_label.platform_geometry(
        Path('unused.png'), settings, 270, 300, 0,
    )
    assert (x, y) == (42, 3)
    assert width > 0
    assert height == 6


def test_reused_qr_badge_does_not_expand_external_marker_column():
    settings = LayoutSettings(
        dpi=25.4, platform_below_marker=True, platform_reuse_qr=True,
        number_gap_mm=5, platform_gap_mm=2,
    )
    block, label, platform = (
        (-15, 0, 10, 10), (-15, 15, 12, 3), (42, 5, 90, 6),
    )
    bx, _by, lx, _ly, px, _py = stacked_coordinates(
        settings, block, label, platform,
    )
    assert bx == lx == -17
    assert px == 42
