"""Gate diagnostic entry points without changing production parameters."""
from PySide6.QtWidgets import QCheckBox


def developer_task_active(window):
    details = window.automation_home.label_quick_panel.details_dialog
    dialog = getattr(details, 'bulk_dialog', None)
    return bool(dialog and dialog.thread is not None)


def build_developer_mode(window, footer):
    checkbox = QCheckBox('开发者模式')
    checkbox.setToolTip('显示用膜历史和批量数据分析；批量分析不生成最终文件。')
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
        panel = window.automation_home.label_quick_panel
        panel.history_button.setVisible(enabled)
        panel.bulk_analysis_button.setVisible(enabled)
        details = panel.details_dialog
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
