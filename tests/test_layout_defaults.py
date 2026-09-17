from automatic_print.layout_engine import LayoutSettings


def test_default_settings_are_print_ready() -> None:
    settings = LayoutSettings()
    assert settings.media_width_mm == 600
    assert settings.spacing_mm == 8
    assert settings.dpi == 300
    assert settings.png_compression_level == 1
    assert settings.png_engine == "pillow"
    assert settings.number_images is True
    assert settings.number_gap_mm == 5
    assert settings.number_font_size_mm == 7.5 * 25.4 / 72
    assert settings.machine_number == "M1"
    assert settings.label_follow_qr is True
    assert settings.allow_rotation is True
    assert settings.rotation_direction == "left"
    assert settings.color_block_enabled is True
    assert settings.color_block_color == "#ff0000"
    assert settings.color_block_width_mm == 10
    assert settings.color_block_height_mm == 10
    assert settings.color_block_position == "left_top"
