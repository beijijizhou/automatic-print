from PySide6.QtWidgets import QFileDialog
from automatic_print.ui.bulk_workbench import BulkWorkbench
from test_developer_mode import window, APP


def test_bulk_root_highlights_immediately_and_survives_cancel_and_restart(tmp_path, monkeypatch):
    prefs = tmp_path/'prefs.ini'
    parent = tmp_path/'selected-parent'
    parent.mkdir()
    owner = window(prefs)
    panel = owner.automation_home.label_quick_panel
    starts = []
    monkeypatch.setattr(BulkWorkbench, 'begin',
                        lambda self, path, _scan=None: starts.append(path))
    monkeypatch.setattr('automatic_print.ui.batch_folder_selection.choose_batch_folders',
                        lambda *_args: {'batches': [], 'errors': [],
                                        'directories': 1, 'platform': ''})
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: str(parent))
    owner.automation_home.start_layout_button.click()
    assert starts == [parent]
    assert str(parent) in panel.selected_source.text()
    assert '已选择排版目录' in panel.selected_source.text()
    assert '#dbeafe' in panel.selected_source.styleSheet()
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: '')
    owner.automation_home.start_layout_button.click()
    assert starts == [parent]
    assert str(parent) in panel.selected_source.text()
    owner.close()
    fresh = window(prefs)
    fresh_panel = fresh.automation_home.label_quick_panel
    assert str(parent) in fresh_panel.selected_source.text()
    assert '已选择排版目录' in fresh_panel.selected_source.text()
    # Selecting the same previous single source must also clear the bulk identity.
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: str(parent))
    fresh.folder.setText(str(parent))
    from automatic_print.ui.quick_fields import show_selected_source
    show_selected_source(fresh_panel, parent, 'multiple', fresh)
    assert fresh.choose_folder()
    assert '已选择：' in fresh_panel.selected_source.text()
    assert '排版目录' not in fresh_panel.selected_source.text()
    fresh.close()
