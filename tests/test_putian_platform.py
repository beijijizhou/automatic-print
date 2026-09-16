from test_developer_mode import window
from PySide6.QtCore import QSettings


def test_experimental_platforms_are_developer_only_and_enable_forty_mm_gap(tmp_path):
    owner = window(tmp_path / 'putian.ini')
    label = owner.label_settings.platform
    quick = owner.automation_home.label_quick_panel.platform

    assert label.findText('莆田') < 0
    assert quick.findText('莆田') < 0
    assert label.findText('Haloo') < 0
    assert quick.findText('Haloo') < 0

    owner.developer_mode_checkbox.setChecked(True)
    assert label.findText('莆田') >= 0
    assert quick.findText('莆田') >= 0
    assert label.findText('Haloo') >= 0
    assert quick.findText('Haloo') >= 0
    quick.setCurrentText('莆田')
    assert label.currentText() == '莆田'
    assert owner.membrane_gap_enabled.isChecked()
    assert owner.membrane_gap.value() == 40
    assert owner._layout_settings().membrane_gap_mm == 40

    owner.membrane_gap_enabled.setChecked(False)
    owner.membrane_gap.setValue(12)
    quick.setCurrentText('Haloo')
    assert label.currentText() == 'Haloo'
    assert owner.membrane_gap_enabled.isChecked()
    assert owner.membrane_gap.value() == 40
    assert owner._layout_settings().platform_name == 'Haloo'
    assert owner._layout_settings().membrane_gap_mm == 40

    owner.developer_mode_checkbox.setChecked(False)
    assert label.currentText() == '隆丰'
    assert label.findText('莆田') < 0
    assert quick.findText('莆田') < 0
    assert label.findText('Haloo') < 0
    assert quick.findText('Haloo') < 0
    owner.close()


def test_saved_haloo_selection_restores_with_forty_mm_default(tmp_path):
    path = tmp_path / 'haloo.ini'
    preferences = QSettings(str(path), QSettings.IniFormat)
    preferences.setValue('developer/enabled', True)
    preferences.setValue('label/platform_name', 'Haloo')
    preferences.setValue('layout/membrane_gap_enabled', False)
    preferences.setValue('layout/membrane_gap_mm', 18)
    preferences.sync()

    owner = window(path)
    assert owner.label_settings.platform.currentText() == 'Haloo'
    assert owner.membrane_gap_enabled.isChecked()
    assert owner.membrane_gap.value() == 40
    assert owner._layout_settings().platform_name == 'Haloo'
    assert owner._layout_settings().membrane_gap_mm == 40
    owner.close()
