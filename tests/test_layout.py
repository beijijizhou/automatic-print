from PIL import Image

from automatic_print.layout import (
    LayoutSettings,
    discover_images,
    generate_layout,
    mm_to_px,
)
from automatic_print.updater import version_tuple


def test_mm_to_px_at_254_dpi() -> None:
    assert mm_to_px(10, 254) == 100


def test_default_settings_are_print_ready() -> None:
    settings = LayoutSettings()
    assert settings.media_width_mm == 600
    assert settings.dpi == 300
    assert settings.png_compression_level == 1
    assert settings.png_engine == "pillow"
    assert settings.number_images is True
    assert settings.number_gap_mm == 5
    assert settings.number_font_size_mm == 10


def test_versions_are_compared_numerically() -> None:
    assert version_tuple("v0.10.0") > version_tuple("0.2.0")


def test_image_discovery_includes_nested_windows_formats(tmp_path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "image.PNG").touch()
    (nested / "photo.jfif").touch()
    (nested / "ignore.txt").touch()

    assert [path.name for path in discover_images(tmp_path)] == [
        "image.PNG",
        "photo.jfif",
    ]


def test_generate_layout_uses_libvips_and_preserves_transparency(tmp_path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    image_path = source / "transparent.png"
    image = Image.new("RGBA", (20, 10), (255, 0, 0, 128))
    image.save(image_path, dpi=(100, 100))

    result = generate_layout(
        [image_path],
        output,
        LayoutSettings(
            media_width_mm=20,
            spacing_mm=0,
            margin_mm=1,
            dpi=100,
            png_compression_level=1,
            png_engine="libvips",
            number_images=False,
        ),
    )

    assert result["png_engine"] == "libvips"
    with Image.open(output / "print.png") as generated:
        assert generated.mode == "RGBA"
        assert generated.getpixel((0, 0))[3] == 0
        placement = result["placements"][0]
        assert generated.getpixel((placement["x_px"], placement["y_px"])) == (
            255,
            0,
            0,
            128,
        )
        assert placement["sequence_number"] == 1


def test_generate_layout_can_number_images(tmp_path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    paths = []
    for number in range(2):
        path = source / f"{number}.png"
        Image.new("RGBA", (100, 100), (255, 0, 0, 255)).save(
            path, dpi=(100, 100)
        )
        paths.append(path)

    result = generate_layout(
        paths,
        output,
        LayoutSettings(
            media_width_mm=60,
            spacing_mm=1,
            margin_mm=1,
            dpi=100,
            number_images=True,
        ),
    )

    assert [item["sequence_number"] for item in result["placements"]] == [1, 2]
    with Image.open(output / "print.png") as generated:
        second = result["placements"][1]
        sample = generated.crop(
            (
                second["number_x_px"],
                second["number_y_px"],
                second["number_x_px"] + second["number_width_px"],
                second["number_y_px"] + second["number_height_px"],
            )
        )
        assert len(set(sample.getdata())) > 2
        assert second["number_y_px"] >= (
            second["y_px"]
            + second["height_px"]
            + mm_to_px(5, 100)
        )


def test_label_positions_stay_outside_image_and_inside_canvas(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    image_path = source / "sample.png"
    Image.new("RGBA", (100, 80), (0, 100, 200, 255)).save(
        image_path, dpi=(100, 100)
    )

    for position in (
        "top",
        "bottom",
        "left",
        "right",
        "top_left",
        "top_right",
        "bottom_left",
        "bottom_right",
    ):
        result = generate_layout(
            [image_path],
            tmp_path / position,
            LayoutSettings(
                media_width_mm=200,
                margin_mm=2,
                dpi=100,
                label_position=position,
                label_text_template="{number} - {date} - {stem}",
                label_date_format="%Y",
            ),
        )
        placement = result["placements"][0]
        assert placement["number_x_px"] >= 0
        assert placement["number_y_px"] >= 0
        assert (
            placement["number_x_px"] + placement["number_width_px"]
            <= result["width_px"]
        )
        assert (
            placement["number_y_px"] + placement["number_height_px"]
            <= result["height_px"]
        )
        if position in {"top", "top_left", "top_right"}:
            assert (
                placement["number_y_px"] + placement["number_height_px"]
                < placement["y_px"]
            )
        elif position in {"bottom", "bottom_left", "bottom_right"}:
            assert placement["number_y_px"] > (
                placement["y_px"] + placement["height_px"]
            )
        elif position == "left":
            assert (
                placement["number_x_px"] + placement["number_width_px"]
                < placement["x_px"]
            )
        else:
            assert placement["number_x_px"] > (
                placement["x_px"] + placement["width_px"]
            )
        if position in {"top_left", "bottom_left"}:
            assert placement["number_x_px"] == placement["x_px"]
        elif position in {"top_right", "bottom_right"}:
            assert (
                placement["number_x_px"] + placement["number_width_px"]
                == placement["x_px"] + placement["width_px"]
            )
