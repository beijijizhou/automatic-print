"""Categorize canonical settings without duplicating controls or preferences."""
from PySide6.QtWidgets import QTabWidget, QWidget, QFormLayout, QSpinBox


def build_settings_navigation(window, source):
    tabs = QTabWidget()
    forms = {}
    for name in ('膜的设置', '排版规则', '标签与文字', '输出与并行'):
        page = QWidget()
        forms[name] = QFormLayout(page)
        forms[name].setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        tabs.addTab(page, name)
    film = {window.cutter_settings.film, window.cutter_settings.printable}
    layout = {window.spacing, window.margin, window.allow_rotation, window.rotation_direction, window.membrane_gap}
    labels = {'标签与文字', '剪膜机色块'}

    def transfer(form, classify):
        while form.rowCount():
            row = form.takeRow(0)
            label = row.labelItem.widget() if row.labelItem else None
            field = row.fieldItem.widget() or row.fieldItem.layout()
            target = forms[classify(label, field)]
            if label:
                target.addRow(label, field)
            else:
                target.addRow(field)

    cutter = window.cutter_settings
    transfer(cutter.layout(), lambda label, field: '膜的设置' if field in film else '排版规则')
    cutter.hide()
    # The empty cutter container is no longer needed as a form row.
    for index in range(source.rowCount()):
        if source.itemAt(index, QFormLayout.FieldRole).widget() is cutter:
            row = source.takeRow(index)
            row.labelItem.widget().deleteLater()
            break
    transfer(source, lambda label, field: '排版规则' if field in layout else (
        '标签与文字' if label and label.text() in labels else '输出与并行'))
    window.bulk_parallelism = QSpinBox()
    window.bulk_parallelism.setRange(1, 8)
    window.bulk_parallelism.setValue(window.preferences.value('developer/bulk_parallelism', 4, int))
    window.bulk_parallelism.setToolTip('独立批次滚动处理；完成一批立即补下一批。启动后使用参数快照。')
    forms['输出与并行'].insertRow(0, '同时处理批次数', window.bulk_parallelism)
    window.print_settings_tabs = tabs
    window.layout_rules_form = forms['排版规则']
    return tabs
