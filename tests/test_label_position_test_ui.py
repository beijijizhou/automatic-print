"""The unified developer test menu runs focused label checks in the background."""

from time import monotonic, sleep

from test_developer_mode import APP, window


def test_label_position_action_uses_one_test_menu_and_reports_result(tmp_path):
    owner = window(tmp_path/'prefs.ini')
    panel = owner.automation_home.label_quick_panel
    assert not panel.test_tools_button.isVisible()
    owner.developer_mode_checkbox.setChecked(True)
    assert panel.test_tools_button.isVisible()
    menu = panel.test_tools_button.menu()
    menu.popup(panel.test_tools_button.mapToGlobal(panel.test_tools_button.rect().bottomLeft()))
    APP.processEvents()
    assert menu.grab().save(str(tmp_path/'unified-test-menu.png'))
    menu.hide()
    action = next(row for row in panel.test_tools_button.menu().actions()
                  if row.text() == '标签位置安全短测…')
    action.trigger()
    dialog = panel.details_dialog.label_position_test_dialog
    assert dialog.isVisible()
    dialog.run_button.click()
    assert dialog.is_running()
    deadline = monotonic()+20
    while dialog.is_running() and monotonic() < deadline:
        APP.processEvents()
        sleep(0.01)
    assert not dialog.is_running(), '短测超出20秒；保留子进程继续完成'
    APP.processEvents()
    assert dialog.status.text().startswith('通过'), dialog.log.toPlainText()
    assert 'passed' in dialog.log.toPlainText()
    dialog.close()
    actions = {row.text(): row for row in menu.actions()}
    actions['DTF随机10批冷启动测试…'].trigger()
    benchmark = panel.details_dialog.cold_benchmark_dialog
    assert benchmark.isVisible() and not benchmark.is_running()
    benchmark.close()
    actions['批量分析文件夹…'].trigger()
    assert panel.details_dialog.bulk_dialog.isVisible()
    panel.details_dialog.bulk_dialog.close()
    owner.close()
