import os
import time
import threading
from types import SimpleNamespace
from pathlib import Path
import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialog, QPlainTextEdit
from automatic_print.ui.main_window import MainWindow
from automatic_print.batch_ui.dialog import AutomationDialog
from automatic_print.automation.batches.supplements.completed import plan_completed_erp_batches
from automatic_print.automation.api.erp.items import BatchRule

APP = QApplication.instance() or QApplication([])


def pump_until(predicate):
    deadline = time.monotonic() + 5
    while not predicate() and time.monotonic() < deadline:
        APP.processEvents()
        time.sleep(.005)
    assert predicate()


def test_completed_preview_shows_style_and_color_before_generation(tmp_path, monkeypatch):
    owner = MainWindow(QSettings(str(tmp_path/'prefs.ini'), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    owner.developer_mode_checkbox.setChecked(True)
    owner.production_platform_download_page.select_platform('Haloo')
    workbench = owner.production_platform_download_page.workbenches['Haloo']
    page = workbench.completed_page
    page.source.setCurrentIndex(1)
    assert page.source.currentText() == '已完成'
    assert page.plan_button.text() == '自动化生成计划'
    assert workbench.main_tabs.tabText(1) == '批次生成'
    assert workbench.generation_sections.indexOf(page) == 1
    calls = []
    monkeypatch.setattr(workbench, '_start_worker', calls.append)
    page.read_button.click()
    assert calls[0].kind == 'completed_erp'
    assert calls[0].value == 30
    group = SimpleNamespace(logistics_code='USPS', order_composition='单项单件',
                            style_name='T恤', style_id='a', color='黑色', face='反面',
                            size_group='S-XL', item_ids=('1',), item_quantities=(('1', 1),),
                            source_batch_codes=('old',))
    result = dict(platform='Haloo', scope=30, data=dict(count=2, groups=(group,),
                                     rules=(BatchRule(1, '默认规则', (), True),)))
    page.show_result(result)
    assert page.table.item(0, 3).text() == 'T恤（ID: a）'
    assert page.table.item(0, 4).text() == '黑色'
    assert page.table.item(0, 5).text() == '反面'
    assert '未纳入 1 项' in page.summary.text()
    page.boxes[0].setChecked(True)
    assert 'T恤（ID: a）｜颜色：黑色' in page.selection_preview.toPlainText()
    confirmation = []
    def reject_after_inspection(dialog):
        confirmation.append(dialog.findChild(QPlainTextEdit).toPlainText())
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(QDialog, 'exec', reject_after_inspection)
    page.generate()
    assert 'T恤（ID: a）｜颜色：黑色' in confirmation[0]
    assert len(calls) == 1
    monkeypatch.setattr(QDialog, 'exec', lambda _dialog: QDialog.DialogCode.Accepted)
    page.generate()
    assert len(calls) == 2
    assert calls[1].action == 'generate_completed_erp'
    assert calls[1].platform_name == 'Haloo'
    assert calls[1].groups == (group,)
    assert calls[1].rule_id == 1
    page.limit.setValue(20)
    page.show_result(result)
    assert page.table.rowCount() == 0
    assert not page.selection_preview.toPlainText()
    owner.close()


@pytest.mark.parametrize('platform_name', ('隆丰', '莆田', 'Haloo'))
def test_completed_plan_tab_is_available_on_every_erp_platform(tmp_path, platform_name):
    owner = MainWindow(QSettings(str(tmp_path/'prefs.ini'), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    owner.show()
    owner.developer_mode_checkbox.setChecked(True)
    owner.workspace_tabs.setCurrentIndex(owner.production_platform_tab_index)
    owner.production_platform_download_page.select_platform(platform_name)
    workbench = owner.production_platform_download_page.workbenches[platform_name]
    page = workbench.completed_page
    workbench.main_tabs.setCurrentIndex(1)
    workbench.generation_sections.setCurrentWidget(page)
    APP.processEvents()
    assert page.platform_name == platform_name
    assert workbench.main_tabs.tabText(1) == '批次生成'
    assert workbench.open_playwright_button.text() == (
        f'打开 {platform_name} Playwright 浏览器'
    )
    assert workbench.generation_sections.tabText(
        workbench.generation_sections.indexOf(page)
    ) == '生产中批次策略'
    assert page.source.currentData() == 5
    assert page.plan_button.text() == '自动化生成计划'
    assert page.plan_button.isVisibleTo(page)
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
                 logistics_sorting_code='USPS', status=9, qty=1) for i in (1, 2)]
    details = {str(i): {'production_images': [{'name': 'A面'}]} for i in (1, 2)}
    groups = plan_completed_erp_batches(rows, details)
    assert groups[0].item_ids == ('1', '2')


def test_completed_preview_keeps_groups_when_rules_are_temporarily_unavailable(tmp_path):
    owner = MainWindow(QSettings(str(tmp_path/'prefs.ini'), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    owner.developer_mode_checkbox.setChecked(True)
    owner.production_platform_download_page.select_platform('Haloo')
    page = owner.production_platform_download_page.workbenches['Haloo'].completed_page
    page.source.setCurrentIndex(1)
    group = SimpleNamespace(logistics_code='GOFO', order_composition='多项多件',
                            style_name='', style_id='', color='', face='正面',
                            size_group='', item_ids=('1', '2'),
                            item_quantities=(('1', 1), ('2', 1)),
                            source_batch_codes=(), order_ids=('order',))
    issue = '批次规则暂时无法读取，当前计划仍可预览；生成按钮已禁用。'

    page.show_result(dict(platform='Haloo', scope=30, source_status=9,
                          data=dict(count=2, groups=(group,), rules=(),
                                    supplemented=(), order_issues={}, rule_issue=issue)))

    assert page.table.rowCount() == 1
    assert issue in page.summary.text()
    page.boxes[0].setChecked(True)
    assert not page.generate_button.isEnabled()
    owner.close()
