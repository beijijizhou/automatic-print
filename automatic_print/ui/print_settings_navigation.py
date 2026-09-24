"""Categorize canonical settings without duplicating controls or preferences."""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QTabWidget, QWidget, QFormLayout, QSpinBox, QCheckBox

from .gateway_key_settings import build_gateway_key_settings


_CUTTER_ROW_STYLE = (
    'background:#fff7ed;color:#9a3412;border:1px solid #fb923c;'
    'border-radius:5px;padding:4px;font-weight:600;'
)


def _highlight_cutter_row(label, field):
    """Make production-paced cutter settings conspicuous in every category tab."""
    if label is not None:
        text = label.text()
        if not text.startswith('● 切膜 · '):
            label.setText('● 切膜 · ' + text)
        label.setStyleSheet(_CUTTER_ROW_STYLE)
        label.setToolTip('切膜机生产参数：修改会影响当前排版与生产节奏。')
    if isinstance(field, QWidget):
        field.setProperty('cutterProductionSetting', True)


def build_settings_navigation(window, source):
    tabs = QTabWidget()
    forms = {}
    for name in ('切膜机', '自动排版', '标签与文字', '输出与并行'):
        page = QWidget()
        forms[name] = QFormLayout(page)
        forms[name].setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        tabs.addTab(page, name)
    cutter = window.cutter_settings
    layout = {window.spacing, window.margin, window.allow_rotation, window.rotation_direction,
              window.auto_fit_width}
    labels = {'标签与文字', '剪膜机色块'}

    cutter_machine = {
        cutter.film, cutter.custom_film, cutter.printable,
        cutter.mode, cutter.auto_knife,
        cutter.knife_change_gap, cutter.transitions,
        cutter.knife, cutter.safety, cutter.marker_offset, cutter.left_marker_lift,
    }
    automatic_layout = {
        cutter.quick_mode, cutter.rotation_zone, cutter.two_zone,
        cutter.force_small_pair, cutter.force_small_pair_sizes,
        cutter.force_small_pair_limit, cutter.tail_rotation,
        cutter.compare_films,
    }

    def transfer(form, classify):
        while form.rowCount():
            row = form.takeRow(0)
            label = row.labelItem.widget() if row.labelItem else None
            field = row.fieldItem.widget() or row.fieldItem.layout()
            category = classify(label, field)
            target = forms[category]
            if category == '切膜机':
                _highlight_cutter_row(label, field)
            if label:
                target.addRow(label, field)
            else:
                target.addRow(field)

    transfer(cutter.layout(), lambda _label, field: (
        '自动排版' if field in automatic_layout else '切膜机'))
    cutter.hide()
    # The empty cutter container is no longer needed as a form row.
    for index in range(source.rowCount()):
        if source.itemAt(index, QFormLayout.FieldRole).widget() is cutter:
            row = source.takeRow(index)
            row.labelItem.widget().deleteLater()
            break
    cutter_fields = {
        window.membrane_gap_enabled, window.membrane_gap, window.job_path,
    }
    transfer(source, lambda label, field: '切膜机' if (
        field in cutter_fields or (label and label.text() == '剪膜机色块')
    ) else (
        '自动排版' if field in layout else (
        '标签与文字' if label and label.text() in labels else '输出与并行'))
    )
    window.bulk_parallelism = QSpinBox()
    window.bulk_parallelism.setRange(1, 8)
    window.bulk_parallelism.setValue(window.preferences.value('developer/bulk_parallelism', 4, int))
    window.bulk_parallelism.setToolTip('独立批次滚动处理；完成一批立即补下一批。启动后使用参数快照。')
    forms['输出与并行'].insertRow(0, '同时处理批次数', window.bulk_parallelism)
    forms['输出与并行'].insertRow(
        1, '工厂服务密钥', build_gateway_key_settings(window),
    )
    window.combine_bulk_batches = QCheckBox('合并所有子文件夹为一个批次')
    window.combine_bulk_batches.setChecked(
        window.preferences.value('layout/combine_bulk_batches', False, bool))
    window.combine_bulk_batches.setToolTip(
        '多批次排版时只生成一个排版任务；直接合并原图清单，不先生成各子批次PNG。')
    def platform_defaults(name, *, initial=False):
        from .parameter_refresh import defer_parameter_refresh
        with defer_parameter_refresh(window):
            platform = name.strip()
            # Keep a deliberate saved Longfeng override on startup; a later
            # platform switch always applies the selected platform's default.
            saved_longfeng = (initial and platform == '隆丰'
                              and window.preferences.contains('layout/membrane_gap_enabled'))
            if platform and not saved_longfeng:
                window.membrane_gap.setValue(40)
                window.membrane_gap_enabled.setChecked(platform != '隆丰')
                window.preferences.setValue('layout/membrane_gap_mm', 40)
                window.preferences.setValue('layout/membrane_gap_enabled', platform != '隆丰')
            if platform.casefold() == 's2b':
                dual_index = window.cutter_settings.mode.findData('dual')
                if dual_index >= 0:
                    window.cutter_settings.mode.setCurrentIndex(dual_index)
                window.combine_bulk_batches.setChecked(True)
                window.cutter_settings.force_small_pair.setChecked(True)
                window.cutter_settings.two_zone.setChecked(True)
                window.cutter_settings.quick_mode.setChecked(False)
                window.cutter_settings.rotation_zone.setChecked(True)
                window.cutter_settings.tail_rotation.setChecked(False)
                for key, value in (
                    ('layout/combine_bulk_batches', True), ('cutter/mode', 'dual'),
                    ('layout/force_small_pair_width', True), ('layout/majority_two_zone', True),
                    ('cutter/quick_mode', False), ('cutter/rotation_zone', True),
                    ('cutter/tail_rotation', False),
                ):
                    window.preferences.setValue(key, value)
    window.apply_platform_defaults = platform_defaults
    window.label_settings.platform.currentTextChanged.connect(platform_defaults)
    platform_defaults(window.label_settings.platform.currentText(), initial=True)
    window.print_settings_tabs = tabs
    window.cutter_rules_form = forms['切膜机']
    window.layout_rules_form = forms['自动排版']
    window.label_rules_form = forms['标签与文字']
    window.output_parallel_form = forms['输出与并行']
    def sync_cutter_only_rows(*_args):
        cutting = cutter.mode.currentData() != 'free'
        for control in (window.membrane_gap_enabled, window.membrane_gap):
            window.cutter_rules_form.setRowVisible(control, cutting)
    cutter.mode.currentIndexChanged.connect(sync_cutter_only_rows)
    sync_cutter_only_rows()
    def fit_current_page(index):
        page = tabs.widget(index)
        if page is None:
            return
        page.layout().activate()
        height = tabs.tabBar().sizeHint().height() + page.sizeHint().height() + 22
        tabs.setFixedHeight(max(120, height))
    window.fit_settings_tabs = fit_current_page
    tabs.currentChanged.connect(
        lambda index: QTimer.singleShot(0, lambda: fit_current_page(index)))
    QTimer.singleShot(0, lambda: fit_current_page(tabs.currentIndex()))
    return tabs
