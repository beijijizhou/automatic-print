import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from automatic_print.runtime.resources import asset_path
from automatic_print.ui.main_window import MainWindow
from automatic_print.ui.previews.markers.data import build_examples
from automatic_print.ui.previews.markers.focus import LabelFocusPreview
from test_marker_examples import wait_for
from test_parallel_film_geometry import settings


APP = QApplication.instance() or QApplication([])


def focus_row(production=False):
    image = Image.new("RGBA", (900, 280), "white")
    pixels = image.tobytes()
    image.close()
    return {
        "focus_pixels": pixels,
        "focus_size": (900, 280),
        "label_text": "609202242008 · 隆丰 · 3XL · M1 · 1",
        "production": production,
        "sample_kind": "production" if production else "haloo",
    }


def test_focus_preview_prefers_current_real_batch_image(tmp_path):
    results = [focus_row(index == 2) for index in range(4)]
    preview = LabelFocusPreview()
    preview.resize(1100, 540)

    preview.set_results(results)
    APP.processEvents()

    assert preview.selector.currentIndex() == 2
    assert not preview.picture.pixmap().isNull()
    assert preview.scroll.minimumHeight() >= 560
    assert "当前批次真实生产图" in preview.note.text()
    assert "真实坐标显示" in preview.note.text()
    assert results[2]["label_text"] in preview.readout.text()
    assert preview.picture.pixmap().width() >= 900
    assert preview.grab().save(str(tmp_path / "label-focus.png"))
    preview.close()


def test_haloo_fallback_has_direct_high_resolution_label_crops():
    rows = build_examples([], settings())

    assert all(row["sample_kind"].startswith("haloo") for row in rows)
    for row in rows:
        assert row["focus_pixels"]
        width, height = row["focus_size"]
        assert 0 < width <= 3200 and 0 < height <= 700
        assert len(row["focus_pixels"]) == width * height * 4


def test_focus_previews_remain_memory_bounded_for_every_case():
    rows = build_examples([], settings())
    assert all(row["focus_size"][0] <= 3200 for row in rows)
    assert all(row["focus_size"][1] <= 700 for row in rows)


def test_focus_preview_uses_bundled_real_haloo_image_as_current_batch(tmp_path):
    window = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    window.department_selector.setCurrentIndex(window.department_selector.findData("dtf"))
    window.startup_update_timer.stop()
    panel = window.automation_home.label_quick_panel
    examples = panel.marker_examples
    real_image = asset_path("haloo-preview-sample.png")
    window.show()
    panel.preview_tabs.setCurrentWidget(examples)
    examples.use_batch({"planned": [(real_image, None)]})
    wait_for(lambda: any(row["production"] for row in examples.results)
             and examples.worker is None and not examples.pending)

    selected = examples.focus.selector.currentIndex()
    row = examples.results[selected]
    assert row["production"] and row["source"] == str(real_image)
    assert row["focus_pixels"] and row["focus_size"][1] >= 100
    image = examples.focus.images[selected]
    pixels = row["focus_pixels"]
    assert bytes.fromhex("dc2626ff") in pixels
    assert bytes.fromhex("d97706ff") in pixels
    assert bytes.fromhex("a21cafff") in pixels
    assert "当前批次真实生产图" in examples.focus.note.text()
    assert examples.focus.images[selected].save(str(tmp_path / "raw-label-focus.png"))
    assert examples.focus.grab().save(str(tmp_path / "real-haloo-label-focus.png"))

    examples.timer.stop()
    window.preference_autosave.timer.stop()
    panel.preview.stop_loading()
    window.close()
