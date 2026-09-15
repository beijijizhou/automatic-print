"""Gate diagnostic entry points without changing production parameters."""
from PySide6.QtWidgets import QCheckBox


def developer_task_active(window):
    details = window.automation_home.label_quick_panel.details_dialog
    dialog = getattr(details, 'bulk_dialog', None)
    production = getattr(details, 'production_bulk_dialog', None)
    return bool((dialog and dialog.thread is not None) or (production and production.thread is not None))


def build_developer_mode(window, footer):
    checkbox = QCheckBox('开发者模式')
    checkbox.setToolTip('显示算法开销和用膜历史等诊断工具；生产排版内容对所有用户可见。')
    window.developer_mode_checkbox = checkbox
    checkbox.setChecked(window.preferences.value('developer/enabled', False, bool))
    footer.addWidget(checkbox)

    def changed(enabled):
        if not enabled and developer_task_active(window):
            checkbox.blockSignals(True)
            checkbox.setChecked(True)
            checkbox.blockSignals(False)
            return
        window.developer_mode_enabled = enabled
        window.quick_header_gap_group.setVisible(True)
        window.layout_rules_form.setRowVisible(window.membrane_gap_enabled, True)
        window.layout_rules_form.setRowVisible(window.membrane_gap, True)
        window.layout_rules_form.setRowVisible(window.cutter_settings.two_zone, True)
        panel = window.automation_home.label_quick_panel
        window.batch_record_group.setVisible(True)
        panel.summary.gap_loss.setVisible(True)
        panel.history_button.setVisible(enabled)
        panel.bulk_analysis_button.setVisible(False)
        panel.algorithm_costs_button.setVisible(enabled)
        panel.summary.film_table.set_reference_mode(False)
        panel.summary.film_table.set_developer_mode(enabled)
        window.label_settings.form.setRowVisible(window.label_settings.source_order, enabled)
        window.cutter_settings.compare_films.setText(
            '比较45/60厘米：常规与旋转（不自动切换）')
        details = panel.details_dialog
        algorithm = getattr(details, 'algorithm_page', None)
        if algorithm is not None:
            if not enabled and details.tabs.currentWidget() is algorithm:
                details.tabs.setCurrentIndex(0)
            details.tabs.setTabVisible(details.tabs.indexOf(algorithm), enabled)
        history = getattr(details, 'history_page', None)
        if history is not None:
            if not enabled and details.tabs.currentWidget() is history:
                details.tabs.setCurrentIndex(0)
            details.tabs.setTabVisible(details.tabs.indexOf(history), enabled)
        if not enabled and hasattr(details, 'bulk_dialog'):
            details.bulk_dialog.hide()
        window.preferences.setValue('developer/enabled', enabled)
        window.preferences.sync()

    checkbox.toggled.connect(changed)
    changed(checkbox.isChecked())
    return checkbox
