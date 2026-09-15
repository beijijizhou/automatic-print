from test_developer_mode import window
from PySide6.QtWidgets import QFileDialog


def make_s2b_root(root):
    for name in ('S','M','L','XL','XXL','3XL','4XL','5XL'):
        (root/name).mkdir(parents=True)
    return root


def test_s2b_is_platform_but_does_not_replace_batch_actions(tmp_path,monkeypatch):
    owner=window(tmp_path/'prefs.ini')
    label=owner.label_settings
    assert label.platform.findText('S2B')>=0
    label.platform.setCurrentText('S2B')
    assert owner.combine_bulk_batches.isChecked()
    assert owner.cutter_settings.force_small_pair.isChecked()
    assert owner.quick_force_small_pair.isChecked()
    assert owner.cutter_settings.two_zone.isChecked()
    assert owner.cutter_settings.rotation_zone.isChecked()
    assert not owner.cutter_settings.quick_mode.isChecked()
    button=owner.automation_home.start_layout_button
    assert button.text()=='单批次排版'
    assert owner.automation_home.label_quick_panel.bulk_generation_button.text()=='多批次排版'
    selected=make_s2b_root(tmp_path/'S2B批次')/'L'
    owner.folder.setText(str(selected))
    monkeypatch.setattr(owner,'choose_folder',lambda:True)
    calls=[]
    monkeypatch.setattr(owner,'generate',lambda **kw:calls.append(kw))
    owner.choose_and_generate()
    assert calls==[{'preview_only':False}]
    owner.save_layout_preferences(notify=False)
    owner.close()
    restored=window(tmp_path/'prefs.ini')
    assert restored.label_settings.platform.currentText()=='S2B'
    assert restored.automation_home.start_layout_button.text()=='单批次排版'
    restored.close()


def test_single_folder_selection_detects_s2b_without_changing_action(tmp_path,monkeypatch):
    root=make_s2b_root(tmp_path/'S2B批次')
    owner=window(tmp_path/'prefs.ini')
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *_:str(root/'3XL'))
    assert owner.choose_folder()
    assert owner.folder.text()==str(root/'3XL')
    assert owner.label_settings.platform.currentText()=='S2B'
    assert owner.combine_bulk_batches.isChecked()
    assert owner.cutter_settings.force_small_pair.isChecked()
    assert owner.cutter_settings.two_zone.isChecked()
    assert owner.cutter_settings.rotation_zone.isChecked()
    assert owner.automation_home.start_layout_button.text()=='单批次排版'
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
