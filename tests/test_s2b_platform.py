from pathlib import Path
from test_developer_mode import window


def test_s2b_is_a_platform_and_single_action_routes_to_multi(tmp_path,monkeypatch):
    owner=window(tmp_path/'prefs.ini')
    label=owner.label_settings
    assert label.platform.findText('S2B')>=0
    label.platform.setCurrentText('S2B')
    button=owner.automation_home.start_layout_button
    assert button.text()=='S2B批次排版'
    assert '尺码子文件夹' in button.toolTip()
    selected=tmp_path/'S2B批次'
    selected.mkdir()
    owner.folder.setText(str(selected))
    monkeypatch.setattr(owner,'choose_folder',lambda:True)
    calls=[]
    monkeypatch.setattr('automatic_print.ui.bulk_workbench.start_bulk',lambda w,p:calls.append((w,p)))
    monkeypatch.setattr(owner,'generate',lambda **kw:None)
    owner.choose_and_generate()
    assert calls==[(owner,Path(selected))]
    owner.save_layout_preferences(notify=False)
    owner.close()
    restored=window(tmp_path/'prefs.ini')
    assert restored.label_settings.platform.currentText()=='S2B'
    assert restored.automation_home.start_layout_button.text()=='S2B批次排版'
    restored.close()
