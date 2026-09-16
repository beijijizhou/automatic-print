from pathlib import Path

from PySide6.QtCore import QUrl

from automatic_print.ui.recent_output import (
    open_recent_output, remember_recent_output, refresh_recent_output_button,
)
from test_developer_mode import window


def test_recent_successful_output_is_persistent_and_openable(tmp_path, monkeypatch):
    owner = window(tmp_path/'prefs.ini')
    button = owner.automation_home.recent_output_button
    assert not button.isEnabled()

    output = tmp_path/'切膜机文件'/'批次609162025022'
    output.mkdir(parents=True)
    remember_recent_output(owner, output)
    assert button.isEnabled()
    assert str(output) in button.toolTip()

    opened = []
    monkeypatch.setattr(
        'automatic_print.ui.recent_output.QDesktopServices.openUrl',
        lambda url: opened.append(url) or True,
    )
    open_recent_output(owner)
    assert opened == [QUrl.fromLocalFile(str(output.resolve()))]

    restored = window(tmp_path/'prefs.ini')
    assert restored.automation_home.recent_output_button.isEnabled()
    assert Path(restored.preferences.value(
        'layout/latest_success_output_folder', '', str)) == output.resolve()

    output.rmdir()
    refresh_recent_output_button(restored)
    assert not restored.automation_home.recent_output_button.isEnabled()
