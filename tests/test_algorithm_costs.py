from test_developer_mode import window, APP
from automatic_print.layout_engine.operation_timing import OperationTiming
from automatic_print.layout_engine.algorithm_costs import STEPS


def test_costs_are_developer_only_and_copyable_without_image_read(tmp_path):
    owner = window(tmp_path/'prefs.ini')
    panel = owner.automation_home.label_quick_panel
    details = panel.details_dialog
    assert not panel.algorithm_costs_button.isVisible()
    details.open_algorithm_costs()
    assert not hasattr(details, 'algorithm_page')
    owner.developer_mode_checkbox.setChecked(True)
    assert panel.algorithm_costs_button.isVisible()
    panel.algorithm_costs_button.click()
    page = details.algorithm_page
    assert details.tabs.currentWidget() is page
    assert page.table.rowCount() == len(STEPS)
    row=next(i for i,step in enumerate(STEPS) if step[0]=='自动刀位整体比较')
    assert 'O(k × n²)' in page.table.item(row, 1).text()
    assert '尚未读取' in page.actual.toPlainText()
    timer = OperationTiming()
    timer.phase('扫描文件名')
    panel.timings.receive(timer.finish())
    page.refresh()
    assert '扫描文件名' in page.actual.toPlainText()
    page.copy_report()
    assert '单件同色同尺码配对' in APP.clipboard().text()
    assert 'O(n²)' in APP.clipboard().text()
    assert page.grab().save(str(tmp_path/'algorithm-costs.png'))
    owner.developer_mode_checkbox.setChecked(False)
    assert not details.tabs.isTabVisible(details.tabs.indexOf(page))
    assert not panel.algorithm_costs_button.isVisible()
    details.close()
    owner.close()
