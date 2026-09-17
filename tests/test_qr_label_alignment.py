from PIL import Image
import cv2

from automatic_print.layout_engine import LayoutSettings
from automatic_print.layout_engine.intake.preparation import item_factory
from automatic_print.layout_engine.labeling.markers.qr_detection import QrLocation
from automatic_print.layout_engine.labeling.markers.qr_detection import detect_qr_location


def _image(tmp_path):
    path = tmp_path / "膜标签.png"
    Image.new("RGB", (100, 80), "white").save(path, dpi=(100, 100))
    return path


def _settings(**values):
    defaults = {
        "dpi": 100,
        "number_font_size_mm": 3,
        "number_gap_mm": 2,
        "allow_rotation": True,
        "color_block_enabled": False,
    }
    return LayoutSettings(**(defaults | values))


def test_label_aligns_beside_detected_qr_without_extra_height(
    tmp_path, monkeypatch
):
    path = _image(tmp_path)
    monkeypatch.setattr(
        item_factory,
        "detect_qr_location",
        lambda _path: QrLocation(0.2, 0.7),
    )

    choices, _labels = item_factory.read_items(
        [path], _settings(), None
    )
    item = choices[0][0]

    assert item.label_rx + item.label_width < item.image_rx
    assert item.footprint_height == item.height
    label_center = item.label_ry + item.label_height / 2
    image_qr_y = item.image_ry + item.height * 0.7
    assert abs(label_center - image_qr_y) <= 1


def test_qr_position_is_recalculated_after_left_rotation(
    tmp_path, monkeypatch
):
    path = _image(tmp_path)
    monkeypatch.setattr(
        item_factory,
        "detect_qr_location",
        lambda _path: QrLocation(0.8, 0.2),
    )

    choices, _labels = item_factory.read_items(
        [path], _settings(rotation_direction="left"), None
    )
    rotated = choices[0][1]

    assert rotated.rotation_degrees == 90
    assert rotated.label_rx + rotated.label_width < rotated.image_rx
    label_center = rotated.label_ry + rotated.label_height / 2
    image_qr_y = rotated.image_ry + rotated.height * 0.2
    assert abs(label_center - image_qr_y) <= 1


def test_missing_qr_uses_configured_fallback_position(
    tmp_path, monkeypatch
):
    path = _image(tmp_path)
    monkeypatch.setattr(
        item_factory, "detect_qr_location", lambda _path: None
    )

    choices, _labels = item_factory.read_items(
        [path], _settings(label_position="bottom"), None
    )
    item = choices[0][0]

    assert item.label_ry > item.image_ry + item.height
    assert item.footprint_height > item.height


def test_detector_finds_qr_in_unicode_filename(tmp_path):
    path = tmp_path / "蜂鸟膜标签.png"
    canvas = Image.new('RGBA', (1000, 1400), 'blue')
    canvas.paste('white', (50, 30, 300, 180))
    canvas.save(path)

    location = detect_qr_location(path)

    assert location is not None
    assert location.x_ratio < 0.5
    assert 0 < location.y_ratio < 0.2
