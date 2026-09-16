"""Gate diagnostic entry points without changing production parameters."""
from PySide6.QtWidgets import QCheckBox


EXPERIMENTAL_PLATFORMS = ('莆田',)


def sync_experimental_platforms(window, enabled):
    canonical = window.label_settings.platform
    quick = window.automation_home.label_quick_panel.platform
    combos = (canonical, quick)
    if enabled:
        for combo in combos:
            for name in EXPERIMENTAL_PLATFORMS:
                if combo.findText(name) < 0:
                    combo.addItem(name)
        return
    if canonical.currentText().strip() in EXPERIMENTAL_PLATFORMS:
        canonical.setCurrentText('隆丰')
    for combo in combos:
        for name in EXPERIMENTAL_PLATFORMS:
            index = combo.findText(name)
            if index >= 0:
                combo.removeItem(index)


def developer_task_active(window):
    details = window.automation_home.label_quick_panel.details_dialog
    dialog = getattr(details, 'bulk_dialog', None)
    production = getattr(details, 'production_bulk_dialog', None)
    return bool((dialog and dialog.thread is not None) or (production and production.thread is not None))


def build_developer_mode(window, footer):
    checkbox = QCheckBox('开发者模式')
    checkbox.setToolTip('显示算法开销、排版历史和尚未开放给普通用户的实验排版功能。')
    window.developer_mode_checkbox = checkbox
    checkbox.setChecked(window.preferences.value('developer/enabled', False, bool))
    footer.addWidget(checkbox)

    def changed(enabled):
        if not enabled and developer_task_active(window):
            checkbox.blockSignals(True)
            checkbox.setChecked(True)
            checkbox.blockSignals(False)
            return
        from .parameter_refresh import defer_parameter_refresh
        with defer_parameter_refresh(window):
            window.developer_mode_enabled = enabled
            sync_experimental_platforms(window, enabled)
            window.apply_platform_defaults(window.label_settings.platform.currentText())
            window.quick_header_gap_group.setVisible(True)
            window.layout_rules_form.setRowVisible(window.membrane_gap_enabled, True)
            window.layout_rules_form.setRowVisible(window.membrane_gap, True)
            window.layout_rules_form.setRowVisible(window.cutter_settings.two_zone, True)
            window.cutter_settings.set_developer_mode(enabled)
            if not enabled:
                window.output_format.setCurrentIndex(
                    max(0, window.output_format.findData('png')))
            window.output_parallel_form.setRowVisible(window.output_format, enabled)
            panel = window.automation_home.label_quick_panel
            window.batch_record_group.setVisible(True)
            panel.summary.gap_loss.setVisible(True)
            panel.history_button.setVisible(enabled)
            panel.bulk_analysis_button.setVisible(enabled)
            panel.algorithm_costs_button.setVisible(enabled)
            panel.developer_tools_label.setVisible(enabled)
            panel.source_order.setVisible(enabled)
            panel.source_order_group.setVisible(enabled)
            panel.reference_films_label.setVisible(enabled)
            window.automation_home.batch_tools.setVisible(enabled)
            panel.summary.film_table.set_reference_mode(enabled)
            window.label_settings.form.setRowVisible(window.label_settings.source_order, enabled)
            window.cutter_settings.compare_films.setText(
                '比较45/60厘米：常规与旋转（不自动切换）')
            details = panel.details_dialog
            for page in ('algorithm_page', 'history_page'):
                widget = getattr(details, page, None)
                if widget is not None:
                    if not enabled and details.tabs.currentWidget() is widget:
                        details.tabs.setCurrentIndex(0)
                    details.tabs.setTabVisible(details.tabs.indexOf(widget), enabled)
            if not enabled and hasattr(details, 'bulk_dialog'):
                details.bulk_dialog.hide()
            window.preferences.setValue('developer/enabled', enabled)
            window.preferences.sync()

    checkbox.toggled.connect(changed)
    changed(checkbox.isChecked())
    return checkbox
