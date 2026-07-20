from automatic_print.layout import LayoutSettings, mm_to_px


def test_mm_to_px_at_254_dpi() -> None:
    assert mm_to_px(10, 254) == 100


def test_default_settings_are_print_ready() -> None:
    settings = LayoutSettings()
    assert settings.media_width_mm == 600
    assert settings.dpi == 300
