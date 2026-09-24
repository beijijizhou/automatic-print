from PySide6.QtWidgets import QCheckBox


def build_width_fit(window):
    field=QCheckBox('仅单排：超宽先旋转，仍放不下时等比缩小（改变打印尺寸）')
    field.setChecked(window.preferences.value('layout/auto_fit_width',True,bool))
    field.setToolTip(
        '只在单列切膜模式生效，双排不自动缩小。'
        '这是自动排版的尺寸恢复策略；原文件不变。')
    field.toggled.connect(lambda value: window.preferences.setValue('layout/auto_fit_width',value))
    window.auto_fit_width=field
