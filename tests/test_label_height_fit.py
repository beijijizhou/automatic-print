from dataclasses import replace

from PIL import Image

from automatic_print.layout_engine.item_factory import read_items
from automatic_print.layout_engine.labels import settings_label_badge
from automatic_print.layout_engine.models import LayoutSettings, mm_to_px


def test_entire_text_including_newlines_fits_reference_height():
    settings = LayoutSettings(label_fit_height=True, label_reference_height_mm=10, number_font_size_mm=50)
    for text in ("CY 1001Mt26", "CY\n1001Mt26", "M11\nCY\n1001Mt26"):
        badge = settings_label_badge(text, settings)
        assert mm_to_px(9.5, settings.dpi) <= badge.height <= mm_to_px(10, settings.dpi)
        assert badge.getpixel((0, 0))[3] == 0
        badge.close()


def test_height_adaptation_stays_beside_image_without_extra_length(tmp_path):
    path = tmp_path / "production.png"
    Image.new("RGBA", (600, 1200)).save(path, dpi=(300, 300))
    settings = LayoutSettings(
        label_fit_height=True, label_reference_height_mm=10,
        number_font_size_mm=50,
        label_text_template="CY 1001Mt26", allow_rotation=False,
        label_position="block_below", color_block_enabled=True,
    )
    items, labels = read_items([path], settings, None)
    item = items[0][0]
    assert item.footprint_height == item.height
    assert item.label_rx + item.label_width < item.block_rx
    badge = settings_label_badge(labels[1], settings)
    assert badge.size == (item.label_width, item.label_height)
    badge.close()
    bigger = settings_label_badge(labels[1], replace(settings, label_reference_height_mm=15))
    assert bigger.height > item.label_height
    bigger.close()


def test_manual_font_cap_can_make_auto_fitted_text_smaller():
    settings = LayoutSettings(label_fit_height=True, number_font_size_mm=3)
    normal = settings_label_badge("CY 1001Mt26", settings)
    small = settings_label_badge("CY 1001Mt26", replace(settings, number_font_size_mm=1.5))
    assert small.height < normal.height
    normal.close()
    small.close()
