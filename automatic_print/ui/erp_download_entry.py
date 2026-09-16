"""Developer-only tab for downloading generated Longfeng ERP batches."""

from PySide6.QtWidgets import QTabWidget

from ..automation_dialog import AutomationDialog


def install_longfeng_erp_tab(window, tabs: QTabWidget) -> AutomationDialog:
    workbench = AutomationDialog(
        tabs,
        local_only=False,
        platform_names=("隆丰",),
        download_only=True,
    )
    index = tabs.addTab(workbench, "隆丰 ERP 下载")
    tabs.setTabToolTip(
        index,
        "读取隆丰已生成批次，下载并解压生产图，只计算排版数据。",
    )

    def sync(_enabled: bool) -> None:
        enabled = window.developer_mode_checkbox.isChecked()
        if not enabled and tabs.currentWidget() is workbench:
            tabs.setCurrentIndex(0)
        tabs.setTabVisible(index, enabled)

    window.developer_mode_checkbox.toggled.connect(sync)
    sync(window.developer_mode_checkbox.isChecked())
    window.longfeng_erp_dialog = workbench
    window.longfeng_erp_tab_index = index
    return workbench
