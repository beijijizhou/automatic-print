from pathlib import Path
from types import SimpleNamespace

import pytest

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


def test_platform_text_is_not_separately_written_into_qr_card(monkeypatch):
    from automatic_print.layout_engine.labeling.platform import platform_label
    monkeypatch.setattr(platform_label, 'detect_guide_band',
                        lambda _path: (_ for _ in ()).throw(AssertionError('card scan')))
    settings = LayoutSettings(
        dpi=25.4, platform_name='隆丰', platform_font_height_mm=6,
        platform_below_marker=True, platform_reuse_qr=True,
        preserve_header_gap=True,
    )
    x, y, width, height = platform_label.platform_geometry(
        Path('unused.png'), settings, 270, 300, 0,
    )
    assert (x, y, width, height) == (0, 0, 0, 0)


@pytest.mark.parametrize('degrees', [0, 90])
def test_final_validation_rejects_old_card_badge_plan(degrees):
    from automatic_print.layout_engine.labeling.markers.marker_space import validate_embedded_marks
    placement = SimpleNamespace(platform_width_px=10, platform_height_px=6,
                                rotation_degrees=degrees)
    config = LayoutSettings(platform_reuse_qr=True)
    with pytest.raises(ValueError, match='禁止在膜标签卡内另行绘制'):
        validate_embedded_marks([(Path('old-plan.png'), placement)], config)


def test_merged_platform_badge_does_not_expand_external_marker_column():
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
    assert px == bx
