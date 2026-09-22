"""Downloading must not implicitly start local layout or lose its output location."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from automatic_print.ui.main_window import MainWindow
from automatic_print.batch_ui.local.processing import process_local_batches
from automatic_print.batch_ui.task.worker import AutomationWorker
APP = QApplication.instance() or QApplication([])

def test_download_completion_opens_folder_when_option_is_checked(
    tmp_path, monkeypatch
):
    from automatic_print.batch_ui.shell import results as result_view

    platform_folder = tmp_path / "隆丰"
    platform_folder.mkdir()
    owner = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    owner.developer_mode_checkbox.setChecked(True)
    workbench = owner.production_platform_download_page.workbenches["隆丰"]
    opened = []
    monkeypatch.setattr(result_view.QMessageBox, "information", lambda *_args: None)
    monkeypatch.setattr(
        result_view.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )

    result_view.present_action_result(
        workbench,
        {
            "type": "downloaded",
            "platform": "隆丰",
            "files": [platform_folder / "batch.zip"],
            "output_folder": str(platform_folder),
        },
    )

    assert [Path(path).resolve() for path in opened] == [platform_folder.resolve()]
    workbench.open_download_folder.setChecked(False)
    result_view.present_action_result(
        workbench,
        {
            "type": "downloaded",
            "platform": "隆丰",
            "files": [platform_folder / "batch.zip"],
            "output_folder": str(platform_folder),
        },
    )
    assert [Path(path).resolve() for path in opened] == [platform_folder.resolve()]
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
