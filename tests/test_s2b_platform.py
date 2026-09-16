from test_developer_mode import window
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog


def make_s2b_root(root):
    for name in ('S','M','L','XL','XXL','3XL','4XL','5XL'):
        (root/name).mkdir(parents=True)
    return root


def test_s2b_is_platform_and_uses_the_unified_layout_action(tmp_path,monkeypatch):
    owner=window(tmp_path/'prefs.ini')
    label=owner.label_settings
    assert label.platform.findText('S2B')>=0
    label.platform.setCurrentText('S2B')
    assert owner.cutter_settings.mode.currentData() == 'dual'
    assert owner.combine_bulk_batches.isChecked()
    assert owner.cutter_settings.force_small_pair.isChecked()
    assert owner.quick_force_small_pair.isChecked()
    assert owner.cutter_settings.two_zone.isChecked()
    assert owner.cutter_settings.rotation_zone.isChecked()
    assert not owner.cutter_settings.quick_mode.isChecked()
    button=owner.automation_home.start_layout_button
    assert button.text()=='开始排版…'
    assert owner.automation_home.label_quick_panel.bulk_generation_button.isHidden()
    selected=make_s2b_root(tmp_path/'S2B批次')/'L'
    owner.folder.setText(str(selected))
    monkeypatch.setattr(owner,'choose_folder',lambda:True)
    calls=[]
    monkeypatch.setattr('automatic_print.ui.bulk_workbench.start_bulk',
                        lambda window,path:calls.append((window,path)))
    owner.choose_and_generate()
    assert calls==[(owner,str(selected))]
    owner.save_layout_preferences(notify=False)
    owner.close()
    restored=window(tmp_path/'prefs.ini')
    assert restored.label_settings.platform.currentText()=='S2B'
    assert restored.automation_home.start_layout_button.text()=='开始排版…'
    restored.close()


def test_single_folder_selection_detects_s2b_without_changing_action(tmp_path,monkeypatch):
    root=make_s2b_root(tmp_path/'S2B批次')
    owner=window(tmp_path/'prefs.ini')
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *_:str(root/'3XL'))
    assert owner.choose_folder()
    assert owner.folder.text()==str(root/'3XL')
    assert owner.label_settings.platform.currentText()=='S2B'
    assert owner.cutter_settings.mode.currentData()=='dual'
    assert owner.combine_bulk_batches.isChecked()
    assert owner.cutter_settings.force_small_pair.isChecked()
    assert owner.cutter_settings.two_zone.isChecked()
    assert owner.cutter_settings.rotation_zone.isChecked()
    assert owner.automation_home.start_layout_button.text()=='开始排版…'
    owner.close()


def test_s2b_detection_requires_a_size_folder_group(tmp_path):
    from automatic_print.layout_engine.platform_detection import detect_selected_platform
    root=tmp_path/'普通批次'
    (root/'L').mkdir(parents=True)
    assert detect_selected_platform(root)==''
    assert detect_selected_platform(root/'L')==''
    s2b=make_s2b_root(tmp_path/'S2B批次')
    assert detect_selected_platform(s2b)=='S2B'
    assert detect_selected_platform(s2b/'5XL')=='S2B'


def test_platform_and_developer_changes_do_not_restart_batch_preview(tmp_path, monkeypatch):
    owner = window(tmp_path/'no-auto-preview.ini')
    preview = owner.automation_home.label_quick_panel.preview
    preview.source_folder = tmp_path
    requests = []
    monkeypatch.setattr(preview.loader, 'request', lambda *args: requests.append(args))
    owner.label_settings.platform.setCurrentText('S2B')
    QTest.qWait(180)
    assert requests == []
    assert not preview.refresh_timer.isActive()
    assert '参数已更新' in preview.production_stage
    owner.developer_mode_checkbox.setChecked(True)
    QTest.qWait(180)
    assert requests == []
    assert not preview.refresh_timer.isActive()
    owner.close()
