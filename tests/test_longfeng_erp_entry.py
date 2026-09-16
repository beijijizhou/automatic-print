import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from automatic_print.ui.main_window import MainWindow
from automatic_print.batch_ui.local.processing import process_local_batches
from automatic_print.batch_ui.task.worker import AutomationWorker


APP = QApplication.instance() or QApplication([])


def test_platform_download_is_multi_select_and_preview_only(tmp_path):
    owner = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    owner.show()
    APP.processEvents()

    index = owner.production_platform_tab_index
    assert not owner.workspace_tabs.isTabVisible(index)
    owner.developer_mode_checkbox.setChecked(True)
    APP.processEvents()
    assert owner.workspace_tabs.isTabVisible(index)

    owner.workspace_tabs.setCurrentIndex(index)
    APP.processEvents()
    page = owner.production_platform_download_page
    assert owner.workspace_tabs.currentWidget() is page
    assert page.platform_checks["隆丰"].isChecked()
    assert not page.platform_checks["莆田"].isChecked()
    assert not page.platform_checks["S2B"].isChecked()
    assert page.platform_tabs.count() == 1
    longfeng = page.workbenches["隆丰"]
    assert longfeng.platform.currentData() == "隆丰"
    assert longfeng.download_preview_only.isChecked()
    assert not longfeng.download_preview_only.isEnabled()
    assert longfeng.download_button.text() == "下载并解压"
    assert longfeng.process_button.isHidden()
    assert longfeng.test_mode.isHidden()
    assert longfeng.download_preview_only.isHidden()

    page.platform_checks["莆田"].setChecked(True)
    APP.processEvents()
    assert page.platform_tabs.count() == 2
    assert page.workbenches["莆田"].platform.currentData() == "莆田"
    page.platform_checks["隆丰"].setChecked(False)
    assert page.platform_tabs.count() == 1
    assert page.platform_tabs.tabText(0) == "莆田"

    page.platform_checks["S2B"].setChecked(True)
    APP.processEvents()
    s2b = page.workbenches["S2B"]
    assert s2b.platform.currentData() == "S2B"
    assert s2b.range_start.isHidden()
    assert s2b.range_end.isHidden()
    assert s2b.range_button.isHidden()
    assert "不会自动启动排版" in s2b.main_tabs.currentWidget().findChildren(
        type(s2b.summary)
    )[0].text()

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
        "automatic_print.batch_ui.local.processing.generate_layout", fake_generate
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


def test_platform_download_never_starts_layout(tmp_path, monkeypatch):
    downloaded = tmp_path / "batch.zip"
    monkeypatch.setattr(
        "automatic_print.batch_ui.task.worker.download_selected_batches",
        lambda *_args, **_kwargs: [downloaded],
    )
    worker = AutomationWorker(
        "download",
        "隆丰",
        output=tmp_path,
        batch_numbers=["609162027027"],
    )
    monkeypatch.setattr(worker, "_save_batch_types", lambda: None)
    monkeypatch.setattr(
        worker,
        "_process_batches",
        lambda: (_ for _ in ()).throw(AssertionError("排版不应启动")),
    )
    results = []
    worker.completed.connect(results.append)

    worker._run_action()

    assert results == [
        {
            "type": "downloaded",
            "platform": "隆丰",
            "files": [downloaded],
            "output_folder": str(tmp_path / "隆丰"),
        }
    ]
