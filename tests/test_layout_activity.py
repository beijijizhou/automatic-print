import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtGui import QIcon
from test_developer_mode import window, APP


@pytest.mark.parametrize('mode',['single','multiple'])
def test_active_layout_button_spins_even_when_disabled(tmp_path,mode):
    owner=window(tmp_path/'prefs.ini')
    activity=owner.layout_activity
    button=activity.buttons[mode]
    original_text=button.text()
    original_icon=button.icon().cacheKey()
    owner.generation_preview.start(mode)
    assert activity.timer.isActive()
    assert activity.active is button
    assert not button.isEnabled()
    assert button.text()==original_text+' · 进行中'
    assert 'color:#1d4ed8' in button.styleSheet()
    first=button.icon().pixmap(24,24,QIcon.Disabled).toImage()
    activity.tick()
    second=button.icon().pixmap(24,24,QIcon.Disabled).toImage()
    assert first != second
    other=activity.buttons['multiple' if mode=='single' else 'single']
    # The unified entry point handles both single- and multi-batch input.
    assert other is button
    owner.generation_preview.end()
    assert not activity.timer.isActive()
    assert button.text()==original_text
    assert button.icon().cacheKey()==original_icon
    assert button.isEnabled()
    owner.close()
