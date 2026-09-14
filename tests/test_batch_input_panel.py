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
    assert panel.summary.isAncestorOf(owner.stop_generation_button)
    assert inputs.findChild(type(inputs), 'singleInput') is not None
    assert inputs.findChild(type(inputs), 'multiInput') is not None
    assert panel.details_button.mapTo(owner, QPoint()).y() > inputs.mapTo(owner, QPoint()).y()
    assert not panel.history_button.isVisible()
    assert not panel.algorithm_costs_button.isVisible()
    APP.processEvents()
    assert owner.grab().save(str(tmp_path/'batch-input-cards.png'))
    owner.close()
