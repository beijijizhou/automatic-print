import os
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from automatic_print.automation.browser.batches import BatchRecord
from automatic_print.ui.main_window import MainWindow
from automatic_print.batch_ui.local.processing import process_local_batches
from automatic_print.batch_ui.task.worker import AutomationWorker
from automatic_print.automation.batches.received.default_multi import DefaultMultiPlan
from automatic_print.batch_ui.platform.view.generation_page import ask_generation_rule


APP = QApplication.instance() or QApplication([])


def test_generation_rule_dialog_preserves_accept_and_cancel(monkeypatch):
    owner = QWidget()
    plan = SimpleNamespace(
        platform_name='隆丰', total_items=2,
        nonempty_items=(SimpleNamespace(
            shipping_method='普通', order_composition='单项单件',
            item_count=2, piece_count=2,
        ),),
    )
    monkeypatch.setattr(QDialog, 'exec', lambda _dialog: QDialog.Accepted)
    assert ask_generation_rule(owner, plan) == '按有面单生成批次规则'
    monkeypatch.setattr(QDialog, 'exec', lambda _dialog: QDialog.Rejected)
    assert ask_generation_rule(owner, plan) is None
    owner.close()


def test_default_multi_preview_worker_finishes_in_generation_tab(tmp_path, monkeypatch):
    owner = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    owner.developer_mode_checkbox.setChecked(True)
    page = owner.production_platform_download_page.workbenches["隆丰"]
    page.main_tabs.setCurrentIndex(1)
    plan = DefaultMultiPlan(
        "741283", 3, (("item", 2),), (("order", ("item",)),)
    )
    monkeypatch.setattr(
        "automatic_print.batch_ui.task.generation_actions.preview_default_multi",
        lambda: plan,
    )

    page.default_multi_preview_button.click()
    deadline = time.monotonic() + 5
    while page.thread is not None and time.monotonic() < deadline:
        APP.processEvents()
        time.sleep(0.01)

    assert page.thread is None
    assert page.pending_default_multi_plan == plan
    assert page.default_multi_generate_button.isEnabled()
    assert page.route_preview_table.item(0, 3).text() == "2"
    owner.close()


def test_platform_download_is_multi_select_and_preview_only(tmp_path):
    owner = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    owner.show()
    APP.processEvents()

    index = owner.production_platform_tab_index
    assert owner.workspace_tabs.isTabVisible(index)
    owner.department_selector.setCurrentIndex(
        owner.department_selector.findData("dtf")
    )
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
    assert longfeng.main_tabs.tabText(1) == "批次生成"
    longfeng.main_tabs.setCurrentIndex(1)
    APP.processEvents()
    assert longfeng.generation_sections.tabText(0) == "已接单筛选预览"
    assert longfeng.generation_sections.tabText(1) == "生产中批次策略"
    assert longfeng.generation_sections.widget(1) is longfeng.completed_page
    assert longfeng.route_preview_table.horizontalHeaderItem(3).text() == "件数"
    assert longfeng.route_preview_button.text() == "读取工艺路线"
    assert longfeng.default_multi_preview_button.text() == "读取默认路线多项多件"
    assert longfeng.default_multi_generate_button.text() == "直接生成批次"
    assert not longfeng.default_multi_generate_button.isEnabled()
    assert longfeng.route_generate_button.text() == "按筛选生成批次"
    assert not longfeng.route_generate_button.isEnabled()
    assert longfeng.preview_rules_button.text() == "读取分类数量"
    longfeng.default_multi_plan_finished(DefaultMultiPlan(
        "741283", 4, (("item-a", 2),), (("order-a", ("item-a",)),)
    ))
    assert longfeng.route_preview_table.item(0, 1).text() == "1"
    assert longfeng.route_preview_table.item(0, 2).text() == "1"
    assert longfeng.route_preview_table.item(0, 3).text() == "2"
    assert longfeng.candidate_orders_label.text().endswith("1 个候选订单")
    assert longfeng.candidate_orders_table.item(0, 0).text() == "order-a"
    assert longfeng.candidate_orders_table.item(0, 2).text() == "2"
    longfeng.main_tabs.setCurrentIndex(0)
    assert longfeng.download_preview_only.isChecked()
    assert not longfeng.download_preview_only.isEnabled()
    assert longfeng.download_button.text() == "下载并解压"
    assert longfeng.automated_print_button.text() == "下载、排版并生成打印文件"
    assert not longfeng.automated_print_button.isHidden()
    assert longfeng.shared_knife_button.text() == '多批次共用刀位生成PRN'
    assert '分别归入常规和旋转文件夹' in longfeng.shared_knife_button.toolTip()
    assert '不比较四种膜规格' in longfeng.shared_knife_button.toolTip()
    assert '主界面' in longfeng.shared_knife_button.toolTip()
    assert not longfeng.shared_knife_button.isHidden()
    assert not hasattr(longfeng, 'order_side_checkbox')
    assert not hasattr(longfeng, 'order_side_control')
    main_order_side = owner.automation_home.label_quick_panel.order_side_checkbox
    assert main_order_side.isHidden()
    assert not main_order_side.isChecked()
    selected_modes = []
    original_download = longfeng._download_selected
    longfeng._download_selected = lambda *, auto_print: selected_modes.append(auto_print)
    longfeng.shared_knife_button.click()
    main_order_side.setChecked(True)
    assert owner.automation_home.label_quick_panel.order_side_action.isChecked()
    longfeng.shared_knife_button.click()
    assert selected_modes == ['shared_knife', 'shared_knife_order_side']
    assert not main_order_side.isChecked()
    assert not owner.automation_home.label_quick_panel.order_side_action.isChecked()
    longfeng._download_selected = original_download
    assert longfeng.open_download_folder.text() == "下载完成后打开文件夹"
    assert longfeng.open_download_folder.isChecked()
    assert not longfeng.open_download_folder.isHidden()
    assert longfeng.process_button.isHidden()
    assert longfeng.test_mode.isHidden()
    assert longfeng.download_preview_only.isHidden()
    assert longfeng.range_start.isEditable()
    assert longfeng.range_end.isEditable()
    assert longfeng.range_start.currentText() == ""
    assert longfeng.table.horizontalHeaderItem(5).text() == "生成批次时间"

    records = [
        BatchRecord(
            "609180001002", 2, 3, "单项多件",
            "2026-09-18 09:30:00", True,
        ),
        BatchRecord(
            "609180001001", 1, 1, "单项单件",
            "2026-09-18 09:20:00", True,
        ),
    ]
    longfeng._display_batch_records(records)
    assert [
        longfeng.range_start.itemText(index)
        for index in range(longfeng.range_start.count())
    ] == ["609180001002", "609180001001"]
    longfeng.range_start.setCurrentIndex(1)
    assert longfeng.range_start.currentText() == "609180001001"
    longfeng.range_end.setEditText("609180001002")
    assert longfeng.range_end.currentText() == "609180001002"
    assert longfeng.table.item(0, 5).text() == "2026-09-18 09:30:00"

    page.platform_checks["莆田"].setChecked(True)
    APP.processEvents()
    assert page.platform_tabs.count() == 2
    assert page.workbenches["莆田"].platform.currentData() == "莆田"
    assert page.workbenches["莆田"].main_tabs.tabText(1) == "批次生成"
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
    assert "RIIN生成PRN" in s2b.main_tabs.currentWidget().findChildren(
        type(s2b.summary)
    )[0].text()

    owner.developer_mode_checkbox.setChecked(False)
    assert not owner.workspace_tabs.isTabVisible(index)
    assert owner.workspace_tabs.currentIndex() == 0
    owner.department_selector.setCurrentIndex(
        owner.department_selector.findData("uv")
    )
    assert owner.workspace_tabs.isTabVisible(index)
    owner.close()


def test_haloo_workbench_preserves_visible_gap_settings(tmp_path):
    owner = MainWindow(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))
    owner.startup_update_timer.stop()
    owner.developer_mode_checkbox.setChecked(True)
    page = owner.production_platform_download_page
    page.platform_checks["Haloo"].setChecked(True)
    APP.processEvents()

    # A stale main-window selection must not leak into Haloo local processing.
    owner.label_settings.platform.setCurrentText("隆丰")
    owner.membrane_gap_enabled.setChecked(False)
    settings = page.workbenches["Haloo"]._current_layout_settings()

    assert settings.platform_name == "Haloo"
    assert settings.membrane_gap_mm == 0
    owner.membrane_gap_enabled.setChecked(True)
    owner.membrane_gap.setValue(45)
    assert page.workbenches["Haloo"]._current_layout_settings().membrane_gap_mm == 45
    owner.close()
