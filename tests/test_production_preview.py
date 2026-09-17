import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from automatic_print.layout_engine import LayoutSettings
from automatic_print.layout_engine.intake.preparation.item_factory import read_items
from automatic_print.ui.production_preview import ProductionPreview


def test_production_sample_uses_one_image_and_real_engine_coordinates(tmp_path):
    app = QApplication.instance() or QApplication([])
    path = tmp_path / "真实生产样板.png"
    Image.new("RGB", (100, 160), "blue").save(path, dpi=(100, 100))
    settings = LayoutSettings(dpi=100, label_follow_qr=False, allow_rotation=False)
    preview = ProductionPreview(lambda: settings)
    preview.use_folder(tmp_path)
    expected, _labels = read_items([path], settings, None)
    assert preview.item == expected[0][0]
    assert preview.path == path
    assert not preview.thumbnail.isNull()
    assert not preview.badge.isNull()
    assert preview.item.block_width > 0
    preview.resize(700, 300)
    image = QImage(preview.size(), QImage.Format_ARGB32)
    preview.render(image)
    assert not image.isNull()
    preview.close()


def test_missing_dpi_preview_is_explicit_and_empty_folder_clears_sample(tmp_path):
    app = QApplication.instance() or QApplication([])
    path = tmp_path / "no-dpi.png"
    Image.new("RGB", (100, 160), "blue").save(path)
    preview = ProductionPreview(lambda: LayoutSettings(dpi=100, allow_rotation=False))
    preview.use_folder(tmp_path)
    assert preview.item.width == 100
    assert "估算" in preview.detail
    preview.use_folder("")
    assert preview.path is None
    assert preview.item is None
    preview.close()


def test_production_preview_uses_selected_batch_folder_in_sequence_label(tmp_path):
    QApplication.instance() or QApplication([])
    batch = tmp_path / "609162025022"
    size = batch / "S"
    size.mkdir(parents=True)
    Image.new("RGB", (100, 160), "blue").save(
        size / "A00001-很长的图片文件名字-Black-S-NO1-1.png", dpi=(100, 100)
    )
    settings = LayoutSettings(
        dpi=100,
        label_source_order_enabled=True,
        label_follow_qr=False,
        allow_rotation=False,
    )
    preview = ProductionPreview(lambda: settings)
    preview.use_folder(batch)

    assert "609162025022" in preview.sample_text()
    assert "很长的图片文件名字" not in preview.sample_text()
    preview.close()
