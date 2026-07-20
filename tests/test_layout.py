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
