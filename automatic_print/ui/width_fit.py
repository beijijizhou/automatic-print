from PySide6.QtWidgets import QCheckBox


def build_width_fit(window):
    field=QCheckBox('超宽先旋转，仍放不下时等比缩小（改变打印尺寸）')
    field.setChecked(window.preferences.value('layout/auto_fit_width',True,bool))
    field.setToolTip('优先让较短边横向；计入刀码、文字和刀位安全区。仅处理超过当前安全占位上限的图片，原文件不变。')
    field.toggled.connect(lambda value: window.preferences.setValue('layout/auto_fit_width',value))
    window.auto_fit_width=field
