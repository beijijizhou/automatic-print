from test_developer_mode import window, APP
from PySide6.QtCore import Qt


def test_department_navigation_defaults_to_independent_uv_workspace(tmp_path):
    owner = window(tmp_path/'departments.ini', department=None)
    selector = owner.department_selector
    assert [selector.itemData(index) for index in range(selector.count())] == [
        'dtf', 'uv', '3d'
    ]
    assert selector.currentData() == 'uv'
    assert owner.department_workspace.currentWidget() is owner.uv_workspace
    assert owner.department_workspace.currentWidget() is not owner.automation_home
    assert owner.windowTitle() == 'UV 自动化打印工作台'
    assert owner.uv_workspace.generate_button.text() == '生成一张UV合成TIFF'
    assert [
        owner.uv_workspace.material.itemText(index)
        for index in range(owner.uv_workspace.material.count())
    ] == [
        '1040', '2030铁', '2030铝', '2030木板', '圆铁', '原铝', '3040',
        '挂钟2525', '挂钟3030', '车牌', '亚克力',
    ]
    owner.uv_workspace.material.setCurrentIndex(
        owner.uv_workspace.material.findData('license_plate')
    )
    assert owner.uv_workspace.finished_size.text() == '30.8 × 15.7 cm'
    assert owner.uv_workspace.placement_size.text() == '30.8 × 15.7 cm'
    assert owner.uv_workspace.capacity.text() == '8 张 / 64 张'
    assert any(
        '右下角' in label.text()
        for label in owner.uv_workspace.findChildren(type(owner.uv_workspace.status))
    )
    assert not owner.automation_home.settings_button.isEnabled()
    assert not owner.automation_home.settings_button.isVisible()

    selector.setCurrentIndex(selector.findData('dtf'))
    assert owner.department_key == 'dtf'
    assert owner.department_workspace.currentWidget() is owner.automation_home
    assert owner.automation_home.settings_button.isEnabled()
    assert owner.automation_home.settings_button.isVisible()
    assert owner.preferences.value('department/current') == 'dtf'

    selector.setCurrentIndex(selector.findData('uv'))
    assert owner.department_workspace.currentWidget() is owner.uv_workspace
    assert not owner.automation_home.settings_button.isEnabled()
    owner.close()


def test_department_change_keeps_running_dtf_task_visible(tmp_path):
    owner = window(tmp_path/'active-department.ini')
    owner.department_selector.setCurrentIndex(
        owner.department_selector.findData('dtf')
    )
    owner.automation_home.thread = object()
    owner.department_selector.setCurrentIndex(
        owner.department_selector.findData('uv')
    )
    assert owner.department_selector.currentData() == 'dtf'
    assert owner.department_workspace.currentWidget() is owner.automation_home
    assert '任务仍在运行' in owner.status.text()
    owner.automation_home.thread = None
    owner.close()


def test_shared_download_does_not_lock_department_navigation(tmp_path):
    owner = window(tmp_path/'shared-download.ini')
    workbench = owner.production_platform_download_page.workbenches['隆丰']
    workbench.thread = object()
    owner.department_selector.setCurrentIndex(
        owner.department_selector.findData('dtf')
    )
    assert owner.department_selector.currentData() == 'dtf'
    assert owner.department_workspace.currentWidget() is owner.automation_home
    workbench.thread = None
    owner.close()


def test_input_card_has_one_layout_action_while_tools_stay_pinned(tmp_path):
    owner = window(tmp_path/'prefs.ini')
    home = owner.automation_home
    panel = home.label_quick_panel
    assert panel.preview.overview
    inputs = home.batch_input_panel
    assert inputs.isAncestorOf(home.manual_layout_button)
    assert inputs.isAncestorOf(home.start_layout_button)
    assert panel.bulk_generation_button.isHidden()
    assert not home.workbench_scroll.isAncestorOf(home.batch_tools)
    assert inputs.isAncestorOf(owner.stop_generation_button)
    assert home.start_layout_button.text() == '开始排版…'
    assert inputs.isAncestorOf(home.preview_only)
    assert inputs.isAncestorOf(owner.combine_bulk_batches)
    assert not home.start_layout_button.icon().isNull()
    assert owner.stop_generation_button.text() == '暂停批次'
    assert not home.batch_tools.isVisible()
    assert not panel.history_button.isVisible()
    assert not panel.test_tools_button.isVisible()
    assert not panel.source_order.isVisible()
    APP.processEvents()
    assert owner.grab().save(str(tmp_path/'batch-input-cards.png'))
    owner.close()


def test_preview_uses_current_folder_or_selects_one_without_printing(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    owner = window(tmp_path/'prefs.ini')
    calls = []
    scan = {'batches': [], 'errors': [], 'directories': 1, 'platform': ''}
    monkeypatch.setattr('automatic_print.ui.batch_folder_selection.choose_batch_folders',
                        lambda *_args: scan)
    monkeypatch.setattr('automatic_print.ui.bulk_workbench.start_bulk',
                        lambda window, path, selected: calls.append((window, path, selected)))
    owner.automation_home.preview_only.setChecked(True)
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: str(tmp_path))
    owner.automation_home.start_layout_button.click()
    assert calls == [(owner, str(tmp_path), scan)]
    owner.folder.clear()
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: '')
    owner.automation_home.start_layout_button.click()
    assert len(calls) == 1
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: str(tmp_path))
    owner.automation_home.start_layout_button.click()
    assert calls == [(owner, str(tmp_path), scan), (owner, str(tmp_path), scan)]
    owner.thread = object()
    owner.automation_home.start_layout_button.click()
    assert len(calls) == 2
    owner.thread = None
    owner.close()


def test_everyday_parameters_are_grouped_and_text_layout_is_default(tmp_path):
    owner = window(tmp_path/'grouped.ini')
    home = owner.automation_home
    panel = home.label_quick_panel
    titles = {group.title() for group in home.batch_input_panel.findChildren(type(home.batch_input_panel))}
    assert {'批次', '输出', '切膜机 · 刀码与补距', '自动排版'} <= titles
    assert home.batch_input_panel.isAncestorOf(owner.quick_header_gap_group)
    assert home.batch_input_panel.isAncestorOf(owner.quick_force_small_pair)
    assert panel.cutter_group.isAncestorOf(owner.quick_header_gap_group)
    assert panel.automatic_layout_group.isAncestorOf(owner.quick_force_small_pair)
    assert panel.automatic_layout_group.isAncestorOf(panel.platform_enabled)
    assert '#fb923c' in panel.cutter_group.styleSheet()
    assert home.batch_input_panel.isAncestorOf(owner.quick_output_width)
    assert home.batch_input_panel.isAncestorOf(panel.source_order)
    assert panel.source_order.isChecked()
    assert panel.source_order_label.text() == '批次文件夹名＋正序/倒序'
    assert panel.source_order_label.textInteractionFlags() & Qt.TextSelectableByMouse
    assert panel.preview_tabs.currentWidget() is not panel.marker_examples
    assert panel.preview_tabs.tabText(panel.preview_tabs.currentIndex()) == '文字排版预览（默认）'
    owner.cutter_settings.mode.setCurrentIndex(
        owner.cutter_settings.mode.findData('free'))
    assert owner.quick_header_gap_group.isHidden()
    assert not owner.quick_force_small_pair.isVisibleTo(owner)
    assert panel.automatic_layout_group.isVisibleTo(owner)
    assert panel.cutter_marker_enabled.isVisibleTo(owner)
    owner.close()


def test_source_order_default_migrates_once_but_keeps_later_user_choice(tmp_path):
    settings = tmp_path/'source-order.ini'
    first = window(settings)
    assert first.label_settings.source_order.isChecked()
    first.label_settings.source_order.setChecked(False)
    first.save_layout_preferences(notify=False)
    first.close()
    restored = window(settings)
    assert not restored.label_settings.source_order.isChecked()
    restored.close()


def test_primary_action_selects_then_generates_and_cancel_never_reuses_old_folder(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    owner = window(tmp_path/'prefs.ini')
    home = owner.automation_home
    calls = []
    scan = {'batches': [], 'errors': [], 'directories': 1, 'platform': ''}
    monkeypatch.setattr('automatic_print.ui.batch_folder_selection.choose_batch_folders',
                        lambda *_args: scan)
    monkeypatch.setattr('automatic_print.ui.bulk_workbench.start_bulk',
                        lambda _window, path, _selected: calls.append(path))
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: str(tmp_path))
    home.start_layout_button.click()
    assert calls == [str(tmp_path)]
    assert home.manual_layout_button is home.start_layout_button
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: '')
    home.start_layout_button.click()
    assert calls == [str(tmp_path)]  # Cancel must not print the previous path.
    owner.thread = object()
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory',
                        lambda *_: (_ for _ in ()).throw(AssertionError('Busy action opened picker')))
    home.start_layout_button.click()
    assert calls == [str(tmp_path)]
    owner.thread = None
    owner.close()
