"""Developer-only entry for downloading generated Longfeng ERP batches."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton


def install_longfeng_erp_entry(window, footer) -> QPushButton:
    button = QPushButton("隆丰 ERP 下载")
    button.setToolTip(
        "读取隆丰已生成批次，下载并解压生产图，只计算排版数据。"
    )
    footer.addWidget(button)

    def open_dialog() -> None:
        dialog = getattr(window, "longfeng_erp_dialog", None)
        if dialog is None:
            from ..automation_dialog import AutomationDialog

            dialog = AutomationDialog(
                window,
                local_only=False,
                platform_names=("隆丰",),
                download_only=True,
            )
            dialog.setWindowFlag(Qt.Window, True)
            dialog.resize(1080, 720)
            window.longfeng_erp_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    button.clicked.connect(open_dialog)

    def sync(enabled: bool) -> None:
        button.setVisible(enabled)
        dialog = getattr(window, "longfeng_erp_dialog", None)
        if not enabled and dialog is not None:
            dialog.hide()

    window.developer_mode_checkbox.toggled.connect(sync)
    sync(window.developer_mode_checkbox.isChecked())
    window.longfeng_erp_button = button
    return button
