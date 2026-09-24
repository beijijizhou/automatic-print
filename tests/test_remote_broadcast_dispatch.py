import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from automatic_print.batch_ui.platform.remote.broadcast import (
    BroadcastBatchDispatcher,
)
from automatic_print.ui.main_window import MainWindow
from PySide6.QtCore import QSettings


APP = QApplication.instance() or QApplication([])


def test_broadcast_probes_every_machine_and_submits_to_every_responder(tmp_path):
    owner = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    owner.developer_mode_checkbox.setChecked(True)
    owner.production_platform_download_page.select_platform("隆丰")
    APP.processEvents()
    workbench = owner.production_platform_download_page.workbenches["隆丰"]
    probed = []
    submitted = []

    def preflight(machine_id, machine_name):
        probed.append((machine_id, machine_name))
        if machine_name == "M2":
            raise RuntimeError("没有回应")
        return {
            "machine_id": machine_id, "machine_name": machine_name,
            "app_version": "0.1.389", "source_online": True,
        }

    def submit(**request):
        submitted.append(request["target_machine_id"])
        return {"id": f"command-{request['target_machine_id']}"}

    dispatcher = BroadcastBatchDispatcher(
        workbench, fetch=lambda: {}, submit=submit, preflight=preflight,
    )
    dispatcher.probes_finished.disconnect(dispatcher._confirm)
    probe_results = []
    dispatcher.probes_finished.connect(probe_results.append)
    candidates = [
        {"machine_id": "id-1", "machine_name": "M1"},
        {"machine_id": "id-2", "machine_name": "M2"},
        {"machine_id": "id-11", "machine_name": "M11", "is_local": True},
    ]

    dispatcher._probe_all(candidates)

    assert sorted(probed) == [("id-1", "M1"), ("id-11", "M11"), ("id-2", "M2")]
    result = probe_results[0]
    assert [item[0]["machine_name"] for item in result["responsive"]] == ["M1", "M11"]
    assert [item[0]["machine_name"] for item in result["rejected"]] == ["M2"]

    dispatcher.submitted.disconnect(dispatcher._show_result)
    submit_results = []
    dispatcher.submitted.connect(submit_results.append)
    dispatcher._responsive = result["responsive"]
    dispatcher._request = {
        "platform": "隆丰", "batch_numbers": ["609241811005"],
        "batch_details": [], "layout_settings": {}, "generate_prn": True,
    }
    dispatcher._submit_all()

    assert sorted(submitted) == ["id-1", "id-11"]
    assert not submit_results[0]["errors"]
    owner.close()


def test_remote_broadcast_button_uses_current_selection(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QCheckBox, QTableWidgetItem

    owner = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    owner.developer_mode_checkbox.setChecked(True)
    owner.production_platform_download_page.select_platform("隆丰")
    APP.processEvents()
    workbench = owner.production_platform_download_page.workbenches["隆丰"]
    workbench.table.setRowCount(1)
    selected = QCheckBox()
    selected.setChecked(True)
    workbench.table.setCellWidget(0, 0, selected)
    workbench.table.setItem(0, 1, QTableWidgetItem("609241811005"))
    requests = []
    monkeypatch.setattr(
        workbench.remote_broadcast_dispatcher, "start",
        lambda *args: requests.append(args) or True,
    )

    workbench.remote_broadcast_button.click()

    platform, batches, settings = requests[0]
    assert workbench.remote_broadcast_button.text() == "发送到所有可应答机器（测试）"
    assert platform == "隆丰"
    assert batches == ["609241811005"]
    assert settings.platform_name == "隆丰"
    owner.close()
