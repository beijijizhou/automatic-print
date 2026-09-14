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
    assert inputs.findChild(type(inputs), 'singleInput') is not None
    assert inputs.findChild(type(inputs), 'multiInput') is not None
    assert panel.details_button.mapTo(owner, QPoint()).y() > inputs.mapTo(owner, QPoint()).y()
    assert not panel.history_button.isVisible()
    assert not panel.algorithm_costs_button.isVisible()
    APP.processEvents()
    assert owner.grab().save(str(tmp_path/'batch-input-cards.png'))
    owner.close()


def test_primary_action_selects_then_generates_and_cancel_never_reuses_old_folder(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    owner = window(tmp_path/'prefs.ini')
    home = owner.automation_home
    calls = []
    monkeypatch.setattr(owner, 'generate', lambda: calls.append(owner.folder.text()))
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
