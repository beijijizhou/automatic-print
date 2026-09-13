from datetime import datetime
from pathlib import Path

from PIL import Image
import pytest

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.item_factory import read_items
from automatic_print.layout_engine.labels import format_label, settings_label_badge


def test_label_cleanup_and_machine_variable():
    assert format_label(
        "CY 1001Mt______26 {机器号}", 1, Path("image.png"),
        datetime(2026, 9, 12), "%Y-%m-%d", "m11",
    ) == "CY 1001Mt26 m11"
    with pytest.raises(ValueError, match="机器号"):
        format_label("{机器号}", 1, Path("a.png"), datetime.now(), "%Y", "m12")


def test_label_stays_below_left_block_when_image_rotates(tmp_path):
    path = tmp_path / "sample.png"
    Image.new("RGBA", (300, 500), (0, 0, 255, 255)).save(path, dpi=(100, 100))
    settings = LayoutSettings(
        dpi=100, label_position="block_below", label_text_template="CY 1001Mt______26",
        number_font_size_mm=3,
    )
    choices, labels = read_items([path], settings, None)
    assert labels[1] == "CY 1001Mt26"
    for item in choices[0]:
        assert item.label_rx + item.label_width == item.block_rx + item.block_width
        assert item.label_ry > item.block_ry + item.block_height
        assert item.label_rx + item.label_width < item.image_rx
        assert item.label_width <= item.block_width
        assert item.footprint_height == item.height


def test_compact_badge_has_no_white_background():
    badge = settings_label_badge(
        "CY 1001Mt26", LayoutSettings(label_position="block_below")
    )
    assert badge.getpixel((0, 0))[3] == 0
    assert badge.getextrema()[3] == (0, 255)
    assert badge.getextrema()[:3] == ((0, 0), (0, 0), (0, 0))
    badge.close()


@pytest.mark.parametrize("engine", ["pillow", "libvips"])
def test_marker_output_retains_transparency_and_machine_record(tmp_path, engine):
    path = tmp_path / "source.png"
    source = Image.new("RGBA", (300, 500), (0, 0, 0, 0))
    source.putpixel((0, 0), (255, 255, 255, 255))
    source.save(path, dpi=(100, 100))
    result = generate_layout(
        [path], tmp_path / "out", LayoutSettings(
            dpi=100, png_engine=engine, allow_rotation=False,
            label_position="block_below", label_text_template="CY______26 {机器号}",
            number_font_size_mm=3, machine_number="m7",
        ),
    )
    assert result["machine_number"] == "m7"
    placement = result["placements"][0]
    with Image.open(tmp_path / "out" / "print.png") as output:
        assert output.getpixel((placement["x_px"], placement["y_px"])) == (255, 255, 255, 255)
        assert output.getpixel((placement["x_px"] + 10, placement["y_px"] + 10))[3] == 0
