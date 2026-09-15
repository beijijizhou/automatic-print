"""Categorize canonical settings without duplicating controls or preferences."""
from PySide6.QtWidgets import QTabWidget, QWidget, QFormLayout, QSpinBox, QCheckBox


def build_settings_navigation(window, source):
    tabs = QTabWidget()
    forms = {}
    for name in ('膜的设置', '排版规则', '标签与文字', '输出与并行'):
        page = QWidget()
        forms[name] = QFormLayout(page)
        forms[name].setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        tabs.addTab(page, name)
    cutter = window.cutter_settings
    film = {cutter.film, cutter.custom_film, cutter.printable,cutter.auto_knife,
            cutter.knife,cutter.safety,cutter.marker_offset,cutter.compare_films}
    layout = {window.spacing, window.margin, window.allow_rotation, window.rotation_direction,
              window.membrane_gap_enabled, window.membrane_gap, window.auto_fit_width}
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

    transfer(cutter.layout(), lambda label, field: '膜的设置' if field in film else (
        '标签与文字' if field is cutter.left_marker_lift else '排版规则'))
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
    window.combine_bulk_batches = QCheckBox('合并所有子文件夹为一个批次')
    window.combine_bulk_batches.setChecked(
        window.preferences.value('layout/combine_bulk_batches', False, bool))
    window.combine_bulk_batches.setToolTip(
        '多批次排版时只生成一个排版任务；直接合并原图清单，不先生成各子批次PNG。')
    def platform_defaults(name):
        platform = name.strip()
        if platform == '莆田' and getattr(window, 'developer_mode_enabled', False):
            window.membrane_gap.setValue(40)
            window.membrane_gap_enabled.setChecked(True)
            window.preferences.setValue('layout/membrane_gap_mm', 40)
            window.preferences.setValue('layout/membrane_gap_enabled', True)
            return
        if platform.casefold() != 's2b':
            return
        dual_index = window.cutter_settings.mode.findData('dual')
        if dual_index >= 0:
            window.cutter_settings.mode.setCurrentIndex(dual_index)
        window.combine_bulk_batches.setChecked(True)
        window.cutter_settings.force_small_pair.setChecked(True)
        window.cutter_settings.two_zone.setChecked(True)
        window.cutter_settings.quick_mode.setChecked(False)
        window.cutter_settings.rotation_zone.setChecked(True)
        window.cutter_settings.tail_rotation.setChecked(False)
        window.preferences.setValue('layout/combine_bulk_batches', True)
        window.preferences.setValue('cutter/mode', 'dual')
        window.preferences.setValue('layout/force_small_pair_width', True)
        window.preferences.setValue('layout/majority_two_zone', True)
        window.preferences.setValue('cutter/quick_mode', False)
        window.preferences.setValue('cutter/rotation_zone', True)
        window.preferences.setValue('cutter/tail_rotation', False)
    window.apply_platform_defaults = platform_defaults
    window.label_settings.platform.currentTextChanged.connect(platform_defaults)
    platform_defaults(window.label_settings.platform.currentText())
    window.print_settings_tabs = tabs
    window.layout_rules_form = forms['排版规则']
    return tabs
