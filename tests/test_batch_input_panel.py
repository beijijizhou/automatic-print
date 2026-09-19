from test_developer_mode import window, APP
from PySide6.QtCore import Qt


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
    assert not panel.bulk_analysis_button.isVisible()
    assert not panel.cold_benchmark_button.isVisible()
    assert not panel.algorithm_costs_button.isVisible()
    assert not panel.source_order.isVisible()
    APP.processEvents()
    assert owner.grab().save(str(tmp_path/'batch-input-cards.png'))
    owner.close()


def test_preview_uses_current_folder_or_selects_one_without_printing(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    owner = window(tmp_path/'prefs.ini')
    calls = []
    monkeypatch.setattr('automatic_print.ui.bulk_workbench.start_bulk',
                        lambda window, path: calls.append((window, path)))
    owner.automation_home.preview_only.setChecked(True)
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: str(tmp_path))
    owner.automation_home.start_layout_button.click()
    assert calls == [(owner, str(tmp_path))]
    owner.folder.clear()
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: '')
    owner.automation_home.start_layout_button.click()
    assert len(calls) == 1
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: str(tmp_path))
    owner.automation_home.start_layout_button.click()
    assert calls == [(owner, str(tmp_path)), (owner, str(tmp_path))]
    owner.thread = object()
    owner.automation_home.start_layout_button.click()
    assert len(calls) == 2
    owner.thread = None
    owner.close()


def test_everyday_parameters_are_grouped_and_marker_preview_is_default(tmp_path):
    owner = window(tmp_path/'grouped.ini')
    home = owner.automation_home
    panel = home.label_quick_panel
    titles = {group.title() for group in home.batch_input_panel.findChildren(type(home.batch_input_panel))}
    assert {'批次', '输出', '排版', '刀码与标签'} <= titles
    assert home.batch_input_panel.isAncestorOf(owner.quick_header_gap_group)
    assert home.batch_input_panel.isAncestorOf(owner.quick_force_small_pair)
    assert home.batch_input_panel.isAncestorOf(owner.quick_output_width)
    assert home.batch_input_panel.isAncestorOf(panel.source_order)
    assert panel.source_order.isChecked()
    assert panel.source_order_label.text() == '批次文件夹名＋正序/倒序'
    assert panel.source_order_label.textInteractionFlags() & Qt.TextSelectableByMouse
    assert panel.preview_tabs.currentWidget() is panel.marker_examples
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
    monkeypatch.setattr('automatic_print.ui.bulk_workbench.start_bulk',
                        lambda _window, path: calls.append(path))
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
