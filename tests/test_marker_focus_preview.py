import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from automatic_print.ui.previews.markers.focus import LabelFocusPreview, label_area
from automatic_print.ui.main_window import MainWindow
from test_marker_examples import sources, wait_for


APP = QApplication.instance() or QApplication([])


def example(production=False):
    item = SimpleNamespace(
        footprint_width=500, footprint_height=250,
        image_rx=50, image_ry=25, width=400, height=200,
        label_rx=250, label_ry=21, label_width=75, label_height=54,
        block_rx=36, block_ry=22, block_width=12, block_height=12,
    )
    region = SimpleNamespace(left=.72, top=0, right=.98, bottom=.25)
    return {
        "item": item,
        "region": region,
        "label_text": "609202242008 · 隆丰 · 3XL · M1 · 1",
        "production": production,
    }


def test_label_area_is_a_real_crop_instead_of_the_full_preview():
    image = QImage(1000, 500, QImage.Format_RGBA8888)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.fillRect(500, 42, 150, 108, QColor("red"))
    painter.end()

    cropped = label_area(image, example())

    assert 150 < cropped.width() < image.width()
    assert 100 < cropped.height() < image.height()
    assert any(cropped.pixelColor(x, y) == QColor("red")
               for x in range(cropped.width()) for y in range(cropped.height()))


def test_focus_preview_prefers_current_batch_and_renders_one_large_image(tmp_path):
    images = []
    results = []
    for index in range(4):
        image = QImage(1000, 500, QImage.Format_RGBA8888)
        image.fill(QColor("white"))
        images.append(image)
        results.append(example(production=index == 2))
    preview = LabelFocusPreview()
    preview.resize(1000, 480)

    preview.set_results(results, images)
    APP.processEvents()

    assert preview.selector.currentIndex() == 2
    assert not preview.picture.pixmap().isNull()
    assert preview.picture.minimumHeight() >= 360
    assert "不改变打印字号" in preview.note.text()
    assert preview.grab().save(str(tmp_path / "label-focus.png"))
    preview.close()


def test_focus_preview_uses_real_marker_render_and_current_batch(tmp_path):
    window = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    window.department_selector.setCurrentIndex(window.department_selector.findData("dtf"))
    window.startup_update_timer.stop()
    panel = window.automation_home.label_quick_panel
    examples = panel.marker_examples
    window.show()
    panel.preview_tabs.setCurrentWidget(examples)
    examples.use_batch({"planned": [(path, None) for path in sources(tmp_path)]})
    wait_for(lambda: any(row["production"] for row in examples.results)
             and examples.worker is None and not examples.pending)

    selected = examples.focus.selector.currentIndex()
    assert examples.results[selected]["production"]
    assert examples.focus.images[selected].width() < examples.images[selected].width()
    assert examples.focus.grab().save(str(tmp_path / "real-label-focus.png"))

    examples.timer.stop()
    window.preference_autosave.timer.stop()
    panel.preview.stop_loading()
    window.close()
