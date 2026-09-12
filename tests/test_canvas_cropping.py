import pytest
from PIL import Image

from automatic_print.layout import LayoutSettings, generate_layout


def _image(path, width=250, height=100):
    Image.new("RGB", (width, height), "blue").save(
        path, dpi=(100, 100)
    )


@pytest.mark.parametrize("engine", ["pillow", "libvips"])
def test_unused_right_side_is_not_added_to_output(tmp_path, engine) -> None:
    path = tmp_path / "image.png"
    _image(path)

    result = generate_layout(
        [path],
        tmp_path / "output",
        LayoutSettings(
            media_width_mm=450 * 25.4 / 100,
            margin_mm=0,
            dpi=100,
            number_images=False,
            color_block_enabled=False,
            allow_rotation=False,
            png_engine=engine,
        ),
    )

    assert result["width_px"] == 250
    placement = result["placements"][0]
    assert placement["x_px"] == 0
    assert result["width_px"] - placement["x_px"] - 250 == 0
    assert result["maximum_width_mm"] == 114.3
    assert result["trimmed_right_mm"] == 50.8
    with Image.open(tmp_path / "output" / "print.png") as output:
        assert output.width == 250


def test_configured_width_remains_layout_maximum(tmp_path) -> None:
    paths = [tmp_path / f"{index}.png" for index in range(2)]
    for path in paths:
        _image(path, width=250)

    result = generate_layout(
        paths,
        tmp_path / "output",
        LayoutSettings(
            media_width_mm=450 * 25.4 / 100,
            spacing_mm=0,
            margin_mm=0,
            dpi=100,
            number_images=False,
            color_block_enabled=False,
            allow_rotation=False,
        ),
    )

    assert result["width_px"] == 250
    assert result["height_px"] == 200
