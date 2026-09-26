"""Gate diagnostic entry points without changing production parameters."""
from PySide6.QtWidgets import QCheckBox
from .full_test_runner import install_full_test_control

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
    erp = getattr(window, 'longfeng_erp_dialog', None)
    benchmark = getattr(details, 'cold_benchmark_dialog', None)
    label_test = getattr(details, 'label_position_test_dialog', None)
    return bool(
        (dialog and dialog.thread is not None)
        or (production and production.thread is not None)
        or (erp and erp.thread is not None)
        or (benchmark and benchmark.is_running())
        or (label_test and label_test.is_running())
        or (getattr(window, 'full_test_controller', None) and window.full_test_controller.is_running())
    )


def bind_developer_tab_visibility(window, tabs, page, index):
    """Keep one developer-only workspace tab synchronized with the mode toggle."""
    def sync(_enabled=False):
        enabled = window.developer_mode_checkbox.isChecked()
        if not enabled and tabs.currentWidget() is page:
            tabs.setCurrentIndex(0)
        tabs.setTabVisible(index, enabled)

    window.developer_mode_checkbox.toggled.connect(sync)
    sync()


def build_developer_mode(window, menu, tools_menu):
    checkbox = QCheckBox('开发者模式')
    checkbox.setToolTip('开启后在下方集中显示打印参数、账号、诊断和测试功能。')
    window.developer_mode_checkbox = checkbox
    checkbox.setChecked(window.preferences.value('developer/enabled', False, bool))
    menu.addWidget(checkbox)
    install_full_test_control(window, tools_menu)

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
            cutting = window.cutter_settings.mode.currentData() != 'free'
            window.quick_header_gap_group.setVisible(cutting)
            window.cutter_rules_form.setRowVisible(window.membrane_gap_enabled, cutting)
            window.cutter_rules_form.setRowVisible(window.membrane_gap, cutting)
            window.layout_rules_form.setRowVisible(window.cutter_settings.two_zone, True)
            window.cutter_settings.set_developer_mode(enabled)
            if not enabled:
                window.output_format.setCurrentIndex(max(0, window.output_format.findData('png')))
            window.quick_output_format_group.setVisible(enabled)
            window.output_parallel_form.setRowVisible(window.output_format, enabled)
            panel = window.automation_home.label_quick_panel
            panel.summary.gap_loss.setVisible(True)
            panel.history_button.setVisible(enabled)
            panel.test_tools_button.setVisible(enabled)
            panel.source_order.setVisible(enabled)
            panel.source_order_control.setVisible(enabled)
            panel.reference_films_label.setVisible(enabled and cutting)
            panel.summary.film_table.set_reference_mode(enabled)
            window.label_settings.form.setRowVisible(window.label_settings.source_order, enabled)
            window.cutter_settings.compare_films.setText('比较45/60厘米：常规与旋转（不自动切换）')
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
            from .departments import sync_dtf_tool_visibility
            sync_dtf_tool_visibility(window)

    checkbox.toggled.connect(changed)
    changed(checkbox.isChecked())
    return checkbox
