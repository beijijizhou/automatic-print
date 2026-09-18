import time
import threading
from types import SimpleNamespace
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from automatic_print.ui.main_window import MainWindow
from automatic_print.batch_ui.dialog import AutomationDialog
from automatic_print.automation.batches.completed import plan_completed_haloo_batches

APP = QApplication.instance() or QApplication([])


def pump_until(predicate):
    deadline = time.monotonic() + 5
    while not predicate() and time.monotonic() < deadline:
        APP.processEvents()
        time.sleep(.005)
    assert predicate()


def test_completed_preview_is_read_only_and_clears_changed_scope(tmp_path, monkeypatch):
    owner = MainWindow(QSettings(str(tmp_path/'prefs.ini'), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    owner.developer_mode_checkbox.setChecked(True)
    owner.production_platform_download_page.platform_checks['Haloo'].setChecked(True)
    workbench = owner.production_platform_download_page.workbenches['Haloo']
    page = workbench.completed_haloo_page
    calls = []
    monkeypatch.setattr(workbench, '_start_worker', calls.append)
    page.read_button.click()
    assert calls[0].kind == 'completed_haloo'
    assert calls[0].value == 30
    group = SimpleNamespace(logistics_code='USPS', order_composition='单项单件',
                            style_name='T恤', style_id='a', color='黑色', face='反面',
                            size_group='S-XL', item_ids=('1',), source_batch_codes=('old',))
    result = dict(scope=30, data=dict(count=2, groups=(group,)))
    page.show_result(result)
    assert page.table.item(0, 4).text() == '反面'
    assert '未纳入 1 项' in page.summary.text()
    assert '未生成批次' in page.summary.text()
    page.limit.setValue(20)
    page.show_result(result)
    assert page.table.rowCount() == 0
    owner.close()


def test_slow_scan_runs_off_gui_thread_and_stale_scope_is_discarded(tmp_path, monkeypatch):
    from automatic_print.automation.batches import local
    entered, release = threading.Event(), threading.Event()
    gui_ident = threading.get_ident()
    identities = []
    def slow_scan(root, platform):
        identities.append(threading.get_ident())
        entered.set()
        assert release.wait(4)
        return [SimpleNamespace(platform_name=platform, batch_number='123',
                image_count=0, modified_at='', folder=root/'123')]
    monkeypatch.setattr(local, 'discover_local_batches', slow_scan)
    dialog = AutomationDialog(local_only=True, platform_names=('Haloo',))
    dialog.output.setText(str(tmp_path/'first'))
    dialog.refresh_local_batches()
    try:
        pump_until(entered.is_set)
        assert identities[0] != gui_ident
        dialog.output.setText(str(tmp_path/'second'))
    finally:
        release.set()
        pump_until(lambda: dialog.thread is None)
    assert dialog.local_table.rowCount() == 0
    dialog.close()


def test_multi_only_snapshot_does_not_require_single_item_style():
    rows = [dict(id=str(i), order_id='order', order_composition=3,
                 logistics_sorting_code='USPS', status=9) for i in (1, 2)]
    details = {str(i): {'production_images': [{'name': 'A面'}]} for i in (1, 2)}
    groups = plan_completed_haloo_batches(rows, details)
    assert groups[0].item_ids == ('1', '2')
