import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QCheckBox, QPushButton, QTableWidgetItem

from automatic_print.batch_ui.task.worker import AutomationWorker
from automatic_print.ui.main_window import MainWindow


APP = QApplication.instance() or QApplication([])


def window(tmp_path):
    owner = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    owner.developer_mode_checkbox.setChecked(True)
    owner.show()
    APP.processEvents()
    return owner


def test_automated_print_action_moved_to_platform_download(tmp_path):
    owner = window(tmp_path)
    page = owner.production_platform_download_page
    page.select_platform("Haloo")
    APP.processEvents()
    workbench = page.workbenches["Haloo"]

    assert not workbench.automated_print_button.isHidden()
    assert workbench.automated_print_button.text() == "下载、排版并生成打印文件"
    assert workbench.select_button.isHidden()
    assert workbench.download_button.isHidden()
    assert not hasattr(workbench, "shared_knife_button")
    assert workbench.main_tabs.currentWidget().isAncestorOf(
        workbench.automated_print_button
    )
    home_labels = [
        button.text()
        for button in owner.automation_home.batch_tools.findChildren(QPushButton)
    ]
    assert "自动生成打印文件…" not in home_labels
    owner.close()


def test_automated_print_action_uses_selected_batches_and_current_settings(
    tmp_path, monkeypatch
):
    owner = window(tmp_path)
    page = owner.production_platform_download_page
    page.select_platform("Haloo")
    APP.processEvents()
    workbench = page.workbenches["Haloo"]
    workbench.output.setText(str(tmp_path))
    workbench.table.setRowCount(1)
    selected = QCheckBox()
    selected.setChecked(True)
    workbench.table.setCellWidget(0, 0, selected)
    workbench.table.setItem(0, 1, QTableWidgetItem("609180613013"))
    workbench.records = [SimpleNamespace(
        batch_number="609180613013", batch_type="单件单件", batch_label="秋季白色 S-XL"
    )]
    workers = []
    monkeypatch.setattr(workbench, "_start_worker", workers.append)

    workbench.automated_print_button.click()

    worker = workers[0]
    assert worker.action == "download"
    assert worker.platform_name == "Haloo"
    assert worker.batch_numbers == ["609180613013"]
    assert worker.batch_labels == {"609180613013": "秋季白色 S-XL"}
    assert worker.auto_print is True
    assert worker.settings.platform_name == "Haloo"
    assert worker.preview_only is False
    owner.close()


def test_remote_print_action_uses_current_selection_and_platform(
    tmp_path, monkeypatch
):
    owner = window(tmp_path)
    page = owner.production_platform_download_page
    page.select_platform("S2B")
    APP.processEvents()
    workbench = page.workbenches["S2B"]
    workbench.table.setRowCount(1)
    selected = QCheckBox()
    selected.setChecked(True)
    workbench.table.setCellWidget(0, 0, selected)
    workbench.table.setItem(0, 1, QTableWidgetItem("609180613013"))
    requests = []
    monkeypatch.setattr(
        workbench.remote_batch_dispatcher, "start",
        lambda *args: requests.append(args) or True,
    )

    workbench.remote_dispatch_button.click()

    platform, batches, settings = requests[0]
    assert platform == "S2B"
    assert batches == ["609180613013"]
    assert settings.platform_name == "S2B"
    owner.close()


def test_download_worker_runs_download_layout_and_riin_in_order(tmp_path, monkeypatch):
    events = []
    archive = tmp_path / "batch.zip"
    monkeypatch.setattr(
        "automatic_print.batch_ui.task.worker.download_selected_batches",
        lambda *_args, **_kwargs: events.append("download") or [archive],
    )
    worker = AutomationWorker(
        "download", "Haloo", output=tmp_path,
        batch_numbers=["609180613013"], settings=object(), auto_print=True,
    )
    monkeypatch.setattr(worker, "_save_batch_types", lambda: events.append("types"))
    processed = {
        "type": "processed", "platform": "Haloo", "batches": [("batch", {})],
        "output_folder": str(tmp_path / "Haloo" / "PROCESSED"),
    }
    monkeypatch.setattr(
        worker, "_process_batches", lambda: events.append("layout") or processed
    )
    monkeypatch.setattr(
        "automatic_print.automation.api.riin.jobs.generate_batch_prns",
        lambda *_args: (events.append("riin") or ([{"batch": "batch"}], [], [])),
    )
    results = []
    worker.completed.connect(results.append)

    worker._run_action()

    assert events == ["download", "types", "layout", "riin"]
    assert results[0]["type"] == "downloaded_processed_and_printed"
    assert results[0]["files"] == [archive]
    assert results[0]["print_files"] == [{"batch": "batch"}]


def test_s2b_prefixed_archive_root_uses_real_batch_for_layout(
    tmp_path, monkeypatch,
):
    from automatic_print.batch_ui.local import processing

    source = (
        tmp_path / "S2B" / "BATCHES"
        / "HS2B014______11_3CF7S82YMH9F_20260924_035438_np7st0f2"
    )
    source.mkdir(parents=True)
    (source / "S" / "design.png").parent.mkdir()
    (source / "S" / "design.png").write_bytes(b"image")
    calls = []
    monkeypatch.setattr(
        processing,
        "generate_layout",
        lambda images, destination, settings, progress, batch_name, **kwargs:
        calls.append((images, destination, batch_name)) or {"filename": "final.png"},
    )

    result = processing.process_local_batches(
        tmp_path, "S2B", ["3CF7S82YMH9F"], {}, object(), None, False,
        lambda _message: None, batch_labels={"3CF7S82YMH9F": "白色 S-XL"},
    )

    assert result["batches"] == [
        ("3CF7S82YMH9F", {"filename": "final.png"})
    ]
    assert result["batch_labels"] == {"3CF7S82YMH9F": "白色 S-XL"}
    assert calls[0][1:] == (
        tmp_path / "S2B" / "PROCESSED" / "3CF7S82YMH9F",
        "3CF7S82YMH9F",
    )


def test_s2b_batch_type_is_saved_inside_prefixed_archive_root(tmp_path):
    from automatic_print.automation.batches.naming import load_batch_type
    from automatic_print.batch_ui.task.automatic_print import (
        save_downloaded_batch_types,
    )

    source = (
        tmp_path / "S2B" / "BATCHES"
        / "质检_6G5GZIGQ3F7O_20260924_035035_f4u6jgom"
    )
    source.mkdir(parents=True)
    (source / "design.png").write_bytes(b"image")

    save_downloaded_batch_types(
        tmp_path, "S2B", {"6G5GZIGQ3F7O": "单项单件"}
    )

    assert load_batch_type(source) == "单项单件"


def test_batch_prns_continue_after_one_riin_failure(tmp_path, monkeypatch):
    from automatic_print.automation.api.riin import jobs

    output = tmp_path / "PROCESSED"
    for batch in ("one", "two"):
        folder = output / batch
        folder.mkdir(parents=True)
        (folder / "final.png").write_bytes(b"png")

    def generate(files, target, _progress):
        if target.stem == "Haloo_one_3件":
            raise RuntimeError("first failed")
        return {"state": "completed", "output": str(target), "bytes": 1234}

    monkeypatch.setattr(jobs, "generate_prn", generate)
    processed = {
        "platform": "Haloo",
        "output_folder": str(output),
        "batches": [
            ("one", {"filename": "final.png", "analysis": {"piece_count": 3}}),
            ("two", {"filename": "final.png", "analysis": {"piece_count": 4}}),
        ],
    }

    completed, errors, skipped = jobs.generate_batch_prns(
        processed, lambda _message: None
    )

    assert [item["batch"] for item in completed] == ["two"]
    assert errors == [{"batch": "one", "error": "first failed"}]
    assert skipped == []
    assert completed[0]["output"].endswith("Haloo_two_4件.prn")


def test_stop_skips_remaining_groups_after_current_riin_task(tmp_path, monkeypatch):
    from automatic_print.automation.api.riin import jobs

    output = tmp_path / "PROCESSED"
    for batch in ("one", "two"):
        folder = output / batch
        folder.mkdir(parents=True)
        (folder / "final.png").write_bytes(b"png")
    monkeypatch.setattr(jobs, "_print_groups", lambda result, route: [
        ("one", ["final.png"]), ("two", ["final.png"]),
    ])
    generated = []
    monkeypatch.setattr(jobs, "generate_prn", lambda files, target, progress:
                        generated.append(str(target)) or {"output": str(target)})
    checks = []
    def stop_requested():
        checks.append(True)
        return len(checks) >= 3

    completed, errors, skipped = jobs.generate_batch_prns({
        "output_folder": str(output),
        "batches": [("one", {"filename": "final.png"}),
                    ("two", {"filename": "final.png"})],
    }, lambda _message: None, stop_requested)

    assert len(generated) == 1
    assert len(completed) == 1
    assert errors == []
    assert skipped == ["one", "two"]


def test_available_prn_path_never_overwrites_existing_file(tmp_path):
    from automatic_print.automation.api.riin.jobs import available_prn_path

    (tmp_path / "batch.prn").write_bytes(b"existing")
    assert available_prn_path(tmp_path, "batch") == tmp_path / "batch-2.prn"


def test_prn_name_uses_platform_batch_and_each_split_group_piece_count(tmp_path, monkeypatch):
    from automatic_print.automation.api.riin import jobs

    output = tmp_path / "PROCESSED"
    for folder_name in ("常规/run", "旋转/run"):
        folder = output / folder_name
        folder.mkdir(parents=True)
    parts = []
    orders = []
    for filename, folder_name, sources, items in (
        ("normal.png", "常规/run", (
            "A-1-T-Black-M-NO1-1.png", "A-1-T-Black-M-NO1-2.png",
        ), (("A-1-T-Black-M-NO1-1.png", "A-1-T-Black-M-NO1-2.png"),)),
        ("rotated.png", "旋转/run", (
            "B-1-T-Black-L-NO1-1.png", "B-1-T-Black-L-NO2-1.png",
        ), (("B-1-T-Black-L-NO1-1.png",), ("B-1-T-Black-L-NO2-1.png",))),
    ):
        (output / folder_name / filename).write_bytes(b"png")
        parts.append({
            "filename": filename,
            "placements": [{"source": source} for source in sources],
        })
        orders.append({"items": [
            {"images": [{"name": source} for source in item]} for item in items
        ]})
    result = {
        "filename": "normal.png", "files": ["normal.png", "rotated.png"],
        "parts": parts, "analysis": {"piece_count": 3, "orders": orders},
    }
    route = {"parts": [
        {"filename": "normal.png", "folder": "常规/run", "knife_signature": [300]},
        {"filename": "rotated.png", "folder": "旋转/run", "knife_signature": [420]},
    ]}
    sent = []
    monkeypatch.setattr(jobs, "generate_prn", lambda files, target, progress:
                        sent.append(target) or {"state": "completed", "output": str(target)})

    completed, errors, skipped = jobs.generate_batch_prns({
        "platform": "S2B", "output_folder": str(output),
        "batches": [("22UJ9KT4VCZA", result)],
        "batch_routes": {"22UJ9KT4VCZA": route},
        "batch_labels": {"22UJ9KT4VCZA": "秋季白色 S-XL"},
    }, lambda _message: None)

    assert not errors and not skipped and len(completed) == 2
    assert [path.name for path in sent] == [
        "S2B_秋季白色 S-XL_1件.prn", "S2B_秋季白色 S-XL_2件.prn",
    ]


def test_early_prn_result_is_labeled_as_still_writing(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    from automatic_print.batch_ui.shell.results import present_action_result

    owner = SimpleNamespace(summary=MagicMock(), log=MagicMock())
    monkeypatch.setattr(
        'automatic_print.batch_ui.shell.results.QMessageBox.information',
        lambda *_args: None,
    )
    present_action_result(owner, {
        'type': 'downloaded_processed_and_printed',
        'platform': 'Haloo', 'batches': [('batch', {})],
        'output_folder': str(tmp_path),
        'print_files': [{'batch': 'batch', 'riin_complete': False}],
    })

    message = owner.summary.setText.call_args.args[0]
    assert '仍在写入 1' in message
    assert '等RIIN完成' in message
