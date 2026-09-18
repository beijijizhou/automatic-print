import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPushButton

from automatic_print.ui.main_window import MainWindow


APP = QApplication.instance() or QApplication([])


def test_automated_layout_is_in_developer_actions(tmp_path):
    owner = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    control = owner.automation_home.automated_layout_control

    assert owner.workspace_tabs.count() == 2
    assert control.run_button.parent() is owner.automation_home.batch_tools
    assert owner.automation_home.batch_tools.isHidden()
    owner.developer_mode_checkbox.setChecked(True)
    assert not owner.automation_home.batch_tools.isHidden()

    labels = [
        button.text() for button in owner.automation_home.batch_tools.findChildren(QPushButton)
    ]
    assert "自动生成打印文件…" in labels
    owner.close()


def test_folder_starts_existing_local_layout_first(tmp_path, monkeypatch):
    from automatic_print.ui import bulk_workbench

    owner = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    source = tmp_path / "batch"
    source.mkdir()
    owner.choose_folder = lambda: owner.folder.setText(str(source)) or True
    started = []
    monkeypatch.setattr(bulk_workbench, "start_bulk", lambda window, folder: started.append(folder))

    page = owner.automated_layout_page
    page.choose_and_start()

    assert started == [source.resolve()]
    assert page.busy
    assert "本地排版" in page.summary.progress.text()
    owner.close()


def test_background_reads_do_not_block_automated_layout(tmp_path, monkeypatch):
    from automatic_print.ui import bulk_workbench

    owner = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    source = tmp_path / "batch"
    source.mkdir()
    owner.choose_folder = lambda: owner.folder.setText(str(source)) or True
    owner.automation_home.thread = object()
    owner.update_thread = object()
    owner.source_update_applying = False
    started = []
    monkeypatch.setattr(
        bulk_workbench, "start_bulk", lambda window, folder: started.append(folder))

    owner.automated_layout_page.choose_and_start()

    assert started == [source.resolve()]
    owner.automation_home.thread = None
    owner.update_thread = None
    owner.automated_layout_page.busy = False
    owner.close()


def test_existing_cutter_files_go_directly_to_riin_without_decoding(
        tmp_path, monkeypatch):
    from automatic_print.ui import automated_layout, bulk_workbench

    owner = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    source = tmp_path / "切膜机文件"
    source.mkdir()
    pngs = [source / "huge-layout.png", source / "huge-layout-2.PNG"]
    for png in pngs:
        png.write_bytes(b"not decoded by this route")
    owner.choose_folder = lambda: owner.folder.setText(str(source)) or True
    started, launched = [], []
    monkeypatch.setattr(
        bulk_workbench, "start_bulk", lambda window, folder: started.append(folder))
    monkeypatch.setattr(automated_layout, "launch_elevated", launched.append)

    page = owner.automated_layout_page
    page.choose_and_start()

    manifest = Path(launched[0][launched[0].index("--manifest") + 1])
    assert started == []
    assert json.loads(manifest.read_text(encoding="utf-8")) == [
        str(path.resolve()) for path in sorted(pngs, key=str)
    ]
    assert "不解压、不二次排版" in page.summary.progress.text()
    page._finish()
    owner.close()


def test_only_local_layout_outputs_are_sent_to_riin(tmp_path, monkeypatch):
    from automatic_print.ui import automated_layout

    launched = []
    manifests = []

    def fake_launch(arguments):
        launched.append(arguments)
        manifest = arguments[arguments.index("--manifest") + 1]
        manifests.append(json.loads(open(manifest, encoding="utf-8").read()))
        report = arguments[arguments.index("--report") + 1]
        with open(report, "w", encoding="utf-8") as handle:
            json.dump({
                "ok": True,
                "automation": {"state": "completed", "output": arguments[-1]},
            }, handle)

    monkeypatch.setattr(automated_layout, "launch_elevated", fake_launch)
    owner = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    page = owner.automated_layout_page
    source = tmp_path / "batch"
    output = tmp_path / "切膜机文件"
    source.mkdir()
    output.mkdir()
    png = output / "final.png"
    png.write_bytes(b"png")
    page.source_path = source
    page.output_path = source / "batch.prn"
    page.busy = True
    page.local_layout_finished({
        "stopped": False,
        "errors": [],
        "records": [{
            "output": str(output),
            "result": {"files": [png.name], "filename": png.name},
        }],
    })
    page._read_report()

    assert launched[0][0] == "automate-layout"
    assert "--manifest" in launched[0]
    assert manifests == [[str(png.resolve())]]
    assert not page.busy
    assert "本地排版和PRN生成已完成，已加入PrintExp" in page.summary.progress.text()
    assert "打印" not in [button.text() for button in page.findChildren(QPushButton)]
    owner.close()


def test_riin_wait_status_uses_shared_summary_and_real_file_size(tmp_path):
    owner = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    page = owner.automated_layout_page
    page.output_path = tmp_path / "writing.prn"
    page.output_path.write_bytes(b"x" * 1_500_000)
    page._file_count = 2
    page._started_at = 0
    page._report_path = tmp_path / "pending.json"

    page._read_report()

    text = page.summary.progress.text()
    assert "RIIN正在写入PRN" in text
    assert "1.5 兆字节" in text
    assert owner.status.text() == text
    owner.close()
