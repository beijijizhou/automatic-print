"""Build the main workbench shell visible after application startup."""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ... import __version__, __version_display__
from ...batch_ui.dialog import AutomationDialog
from ..developer_mode import build_developer_mode
from ..erp_download_entry import install_production_platform_tab


def build_home(window) -> None:
    window.automation_home = AutomationDialog(window)
    window.version_label = QLabel(f"版本 {__version_display__}")
    window.version_label.setToolTip(f"内部版本：{__version__}")
    window.check_update_button = QPushButton("检查更新")
    window.check_update_button.clicked.connect(
        lambda: window.check_for_updates(False)
    )

    footer = QHBoxLayout()
    footer.addWidget(window.version_label)
    footer.addStretch()
    window.automation_home.settings_button.setMinimumHeight(36)
    footer.addWidget(window.automation_home.settings_button)
    footer.addWidget(window.check_update_button)
    build_developer_mode(window, footer)

    window.workspace_tabs = QTabWidget()
    window.workspace_tabs.addTab(window.automation_home, "本地排版")
    install_production_platform_tab(window, window.workspace_tabs)

    layout = QVBoxLayout()
    layout.addWidget(window.build_update_status())
    layout.addWidget(window.workspace_tabs)
    layout.addLayout(footer)
    container = QWidget()
    container.setLayout(layout)
    window.setCentralWidget(container)
