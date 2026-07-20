from automatic_print.layout import LayoutSettings, discover_images, mm_to_px
from automatic_print.updater import version_tuple


def test_mm_to_px_at_254_dpi() -> None:
    assert mm_to_px(10, 254) == 100


def test_default_settings_are_print_ready() -> None:
    settings = LayoutSettings()
    assert settings.media_width_mm == 600
    assert settings.dpi == 300


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
