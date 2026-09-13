from dataclasses import replace

import numpy as np
import pytest
from PIL import Image

from automatic_print.layout_engine.membrane_region import MembraneRegion, region_from_ink
from automatic_print.layout_engine import dynamic_label, item_factory
from automatic_print.layout_engine.models import LayoutSettings
from automatic_print.layout_engine.planner import plan_layout
from automatic_print.layout_engine.pillow_renderer import _prepare


def test_isolated_header_includes_text_but_not_artwork():
    ink = np.zeros((500, 300), dtype=bool)
    ink[10:60, 200:250] = True
    ink[20:55, 20:190] = True
    ink[150:490, 30:290] = True
    points = np.array([[200, 10], [250, 10], [250, 59], [200, 59]])
    region = region_from_ink(ink, points)
    assert region.top <= 10/500
    assert region.bottom < 70/500
    assert region.left == 20/300
    ink[60:151, 50:60] = True
    assert region_from_ink(ink, points) is None


def test_dynamic_text_matches_detected_height_and_bounded_width(tmp_path, monkeypatch):
    path = tmp_path / "生产图片.png"
    Image.new("RGBA", (1000, 2000)).save(path, dpi=(300, 300))
    region = MembraneRegion(.1, .02, .9, .12)
    monkeypatch.setattr(dynamic_label, "detect_membrane_region", lambda _: region)
    monkeypatch.setattr(item_factory, "detect_membrane_region", lambda _: region)
    settings = LayoutSettings(label_detect_region=True, allow_rotation=False)
    badge = dynamic_label.source_label_badge("CY 1001Mt26", settings, path)
    assert badge.height == 200
    assert badge.width <= 800
    badge.close()
    rotated = dynamic_label.source_label_badge("CY 1001Mt26", settings, path, 90)
    assert rotated.height == 800
    assert rotated.width <= 200
    rotated.close()
    items, _ = item_factory.read_items([path], settings, None)
    assert items[0][0].footprint_height == items[0][0].height
    monkeypatch.setattr(dynamic_label, "detect_membrane_region", lambda _: None)
    with pytest.raises(ValueError, match="未使用默认高度"):
        dynamic_label.source_label_badge("CY", settings, path)


def test_label_changes_side_with_rotated_membrane_header(tmp_path, monkeypatch):
    path = tmp_path / "旋转标签.png"
    Image.new("RGBA", (1000, 2000)).save(path, dpi=(300, 300))
    region = MembraneRegion(.6, .02, .95, .12)
    monkeypatch.setattr(dynamic_label, "detect_membrane_region", lambda _: region)
    monkeypatch.setattr(item_factory, "detect_membrane_region", lambda _: region)
    for degrees, side in ((0, "right"), (90, "left"), (-90, "right"), (180, "left")):
        settings = LayoutSettings(label_detect_region=True, allow_rotation=False,
                                  manual_rotations=((str(path.resolve()), degrees),))
        items, _ = item_factory.read_items([path], settings, None)
        item = items[0][0]
        if side == "right":
            assert item.label_rx >= item.image_rx + item.width
        else:
            assert item.label_rx + item.label_width < item.image_rx
        reference = region.rotated(degrees)
        center = item.image_ry + (reference.top+reference.bottom)/2 * item.height
        assert abs(item.label_ry + item.label_height/2 - center) <= 1
        assert item.block_rx + item.block_width <= item.image_rx


@pytest.mark.parametrize("degrees", [90, -90, 180])
def test_manual_rotation_used_by_planner_and_renderer(tmp_path, degrees):
    path = tmp_path / "图片.png"
    source = Image.new("RGBA", (100, 200), "white")
    source.putpixel((0, 0), (255, 0, 0, 255))
    source.save(path, dpi=(300, 300))
    settings = LayoutSettings(number_images=False, color_block_enabled=False, allow_rotation=True,
                              manual_rotations=((str(path.resolve()), degrees),))
    planned, *_ = plan_layout([path], settings, None)
    placement = planned[0][1]
    assert placement.rotation_degrees == degrees
    image, _ = _prepare(planned[0])
    assert image.size == ((200, 100) if degrees % 180 else (100, 200))
    corner = {90: (0, 99), -90: (199, 0), 180: (99, 199)}[degrees]
    assert image.getpixel(corner) == (255, 0, 0, 255)
    image.close()
