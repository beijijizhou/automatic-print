from test_developer_mode import window


def test_putian_is_developer_only_and_enables_forty_mm_gap(tmp_path):
    owner = window(tmp_path / 'putian.ini')
    label = owner.label_settings.platform
    quick = owner.automation_home.label_quick_panel.platform

    assert label.findText('莆田') < 0
    assert quick.findText('莆田') < 0

    owner.developer_mode_checkbox.setChecked(True)
    assert label.findText('莆田') >= 0
    assert quick.findText('莆田') >= 0
    quick.setCurrentText('莆田')
    assert label.currentText() == '莆田'
    assert owner.membrane_gap_enabled.isChecked()
    assert owner.membrane_gap.value() == 40
    assert owner._layout_settings().membrane_gap_mm == 40

    owner.developer_mode_checkbox.setChecked(False)
    assert label.currentText() == '隆丰'
    assert label.findText('莆田') < 0
    assert quick.findText('莆田') < 0
    owner.close()
