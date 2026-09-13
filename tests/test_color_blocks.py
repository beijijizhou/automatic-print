import pytest
from PIL import Image

from automatic_print.layout import LayoutSettings, generate_layout


@pytest.mark.parametrize("engine", ["pillow", "libvips"])
def test_red_color_block_is_same_height_and_exact_size(
    tmp_path, engine
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    path = source / "sample.png"
    Image.new("RGB", (100, 80), "blue").save(path, dpi=(100, 100))
    result = generate_layout(
        [path],
        tmp_path / "output",
        LayoutSettings(
            media_width_mm=100,
            margin_mm=0,
            dpi=100,
            number_images=False,
            color_block_enabled=True,
            color_block_position="left_top",
            color_block_gap_mm=5,
            png_engine=engine,
        ),
    )

    placement = result["placements"][0]
    assert placement["color_block_width_px"] == 39
    assert placement["color_block_height_px"] == 39
    assert placement["color_block_x_px"] == 0
    assert (
        placement["color_block_y_px"] == placement["y_px"]
    )
    assert placement["color_block_x_px"] < placement["x_px"]
    assert placement["footprint_height_px"] == placement["height_px"]
    with Image.open(tmp_path / "output" / result["filename"]) as output:
        assert output.getpixel(
            (
                placement["color_block_x_px"],
                placement["color_block_y_px"],
            )
        ) == (255, 0, 0, 255)


def test_legacy_right_position_is_forced_to_image_left(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    path = source / "sample.png"
    Image.new("RGB", (100, 80), "blue").save(path, dpi=(100, 100))
    result = generate_layout(
        [path],
        tmp_path / "output",
        LayoutSettings(
            media_width_mm=100,
            margin_mm=0,
            dpi=100,
            number_images=False,
            color_block_enabled=True,
            color_block_position="right",
            color_block_gap_mm=5,
            color_block_offset_x_mm=5,
        ),
    )

    placement = result["placements"][0]
    assert placement["footprint_width_px"] > placement["width_px"]
    assert (
        placement["color_block_x_px"]
        + placement["color_block_width_px"]
        <= placement["x_px"]
    )
    assert placement["color_block_x_px"] == 0


def test_positive_offset_cannot_move_color_block_to_right(tmp_path) -> None:
    path = tmp_path / "sample.png"
    Image.new("RGB", (100, 80), "blue").save(path, dpi=(100, 100))
    result = generate_layout(
        [path],
        tmp_path / "output",
        LayoutSettings(
            media_width_mm=100,
            margin_mm=0,
            dpi=100,
            number_images=False,
            color_block_position="left",
            color_block_offset_x_mm=100,
        ),
    )

    placement = result["placements"][0]
    assert (
        placement["color_block_x_px"]
        + placement["color_block_width_px"]
        <= placement["x_px"]
    )


def test_color_block_realigns_after_image_rotation(tmp_path) -> None:
    path = tmp_path / "wide.png"
    Image.new("RGB", (80, 30), "blue").save(path, dpi=(100, 100))
    result = generate_layout(
        [path],
        tmp_path / "output",
        LayoutSettings(
            media_width_mm=26,
            margin_mm=0,
            dpi=100,
            number_images=False,
            color_block_position="left_top",
        ),
    )

    placement = result["placements"][0]
    assert placement["rotation_degrees"] == 90
    assert placement["color_block_y_px"] == placement["y_px"]
    assert placement["footprint_height_px"] == placement["height_px"]
