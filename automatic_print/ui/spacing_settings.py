"""Describe spacing according to the active production geometry."""


def bind_spacing_description(form, window):
    label = form.labelForField(window.spacing)

    def refresh(*_args):
        free = window.cutter_settings.mode.currentData() == 'free'
        label.setText('自由排版图片间距（毫米）' if free else '上下垂直间距（毫米）')
        window.spacing.setToolTip(
            '自由排版不使用固定刀位，此值同时用于水平和垂直间距。' if free else
            '默认上下垂直间距为 5 毫米，可修改并保存。'
            '水平距离由整批刀位、分区及色块位置计算，不额外叠加此间距。'
        )
        label.setToolTip(window.spacing.toolTip())

    window.cutter_settings.mode.currentIndexChanged.connect(refresh)
    refresh()
