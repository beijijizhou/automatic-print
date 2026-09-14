from PySide6.QtCore import QPoint
from test_developer_mode import window, APP


def test_input_cards_group_single_and_multiple_while_details_stay_below(tmp_path):
    owner = window(tmp_path/'prefs.ini')
    home = owner.automation_home
    panel = home.label_quick_panel
    inputs = home.batch_input_panel
    assert inputs.isAncestorOf(home.manual_layout_button)
    assert inputs.isAncestorOf(home.start_layout_button)
    assert inputs.isAncestorOf(panel.bulk_generation_button)
    assert not inputs.isAncestorOf(panel.details_button)
    assert panel.summary.isAncestorOf(panel.details_button)
    assert inputs.isAncestorOf(owner.stop_generation_button)
    assert home.start_layout_button.text() == '单批次排版'
    assert panel.bulk_generation_button.text() == '多批次排版'
    assert inputs.isAncestorOf(home.preview_only)
    single = home.start_layout_button.icon().pixmap(24, 24).toImage()
    multiple = panel.bulk_generation_button.icon().pixmap(24, 24).toImage()
    assert single != multiple  # Verify after the global style has been applied.
    assert owner.stop_generation_button.text() == '暂停批次'
    assert panel.details_button.mapTo(owner, QPoint()).y() > inputs.mapTo(owner, QPoint()).y()
    assert not panel.history_button.isVisible()
    assert not panel.algorithm_costs_button.isVisible()
    APP.processEvents()
    assert owner.grab().save(str(tmp_path/'batch-input-cards.png'))
    owner.close()


def test_preview_uses_current_folder_or_selects_one_without_printing(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    owner = window(tmp_path/'prefs.ini')
    calls = []
    monkeypatch.setattr(owner, 'generate', lambda **kwargs: calls.append(kwargs))
    owner.automation_home.preview_only.setChecked(True)
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: str(tmp_path))
    owner.automation_home.start_layout_button.click()
    assert calls == [{'preview_only': True}]
    owner.folder.clear()
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: '')
    owner.automation_home.start_layout_button.click()
    assert len(calls) == 1
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: str(tmp_path))
    owner.automation_home.start_layout_button.click()
    assert calls == [{'preview_only': True}, {'preview_only': True}]
    owner.thread = object()
    owner.automation_home.start_layout_button.click()
    assert len(calls) == 2
    owner.thread = None
    owner.close()


def test_primary_action_selects_then_generates_and_cancel_never_reuses_old_folder(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    owner = window(tmp_path/'prefs.ini')
    home = owner.automation_home
    calls = []
    monkeypatch.setattr(owner, 'generate', lambda **_: calls.append(owner.folder.text()))
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
