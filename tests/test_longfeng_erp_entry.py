import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from automatic_print.ui.main_window import MainWindow
from automatic_print.batch_ui.processing import process_local_batches


APP = QApplication.instance() or QApplication([])


def test_longfeng_download_is_developer_only_and_preview_only(tmp_path):
    owner = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    owner.show()
    APP.processEvents()

    index = owner.longfeng_erp_tab_index
    assert not owner.workspace_tabs.isTabVisible(index)
    owner.developer_mode_checkbox.setChecked(True)
    APP.processEvents()
    assert owner.workspace_tabs.isTabVisible(index)

    owner.workspace_tabs.setCurrentIndex(index)
    APP.processEvents()
    dialog = owner.longfeng_erp_dialog
    assert dialog.isVisible()
    assert owner.workspace_tabs.currentWidget() is dialog
    assert dialog.platform.currentData() == "隆丰"
    assert dialog.main_tabs.currentIndex() == 2
    assert not dialog.main_tabs.isTabVisible(0)
    assert not dialog.main_tabs.isTabVisible(1)
    assert dialog.download_preview_only.isChecked()
    assert not dialog.download_preview_only.isEnabled()
    assert not dialog.test_mode.isChecked()
    assert not dialog.test_mode.isEnabled()

    owner.developer_mode_checkbox.setChecked(False)
    assert not owner.workspace_tabs.isTabVisible(index)
    assert owner.workspace_tabs.currentIndex() == 0
    owner.close()


def test_downloaded_batch_preview_does_not_render_output(tmp_path, monkeypatch):
    batch = tmp_path / "隆丰" / "BATCHES" / "609162027027"
    batch.mkdir(parents=True)
    (batch / "sample.png").write_bytes(b"not-decoded-by-this-test")
    calls = []

    def fake_generate(images, destination, settings, *args, **kwargs):
        calls.append((images, destination, kwargs))
        return {"preview_only": True, "saved_length_m": 0}

    monkeypatch.setattr(
        "automatic_print.batch_ui.processing.generate_layout", fake_generate
    )
    result = process_local_batches(
        tmp_path,
        "隆丰",
        [batch.name],
        {},
        object(),
        None,
        False,
        lambda _message: None,
        preview_only=True,
    )

    assert result["preview_only"] is True
    assert calls[0][2]["preview_only"] is True
    assert not (tmp_path / "隆丰" / "PREVIEW").exists()
