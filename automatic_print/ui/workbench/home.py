"""Build the main workbench shell visible after application startup."""

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ... import __version__, __version_display__
from ...batch_ui.dialog import AutomationDialog
from ..developer_mode import build_developer_mode
from ..departments import build_department_workspace
from ..erp_download_entry import install_production_platform_tab
from ..machine_status_board import install_machine_status_tab
from ..cutter_mode_banner import CutterModeBanner
from ..global_activity_center import GlobalActivityCenter


def build_home(window) -> None:
    window.automation_home = AutomationDialog(window)
    window.version_label = QLabel(f"版本 {__version_display__}")
    window.version_label.setToolTip(f"内部版本：{__version__}")

    window.dtf_tools_bar = QGroupBox("固定菜单")
    tools_policy = window.dtf_tools_bar.sizePolicy()
    tools_policy.setVerticalPolicy(QSizePolicy.Maximum)
    window.dtf_tools_bar.setSizePolicy(tools_policy)
    fixed_menu = QVBoxLayout(window.dtf_tools_bar)
    top_menu = QHBoxLayout()
    top_menu.addWidget(window.version_label)
    window.check_update_button = QPushButton("检查更新")
    window.check_update_button.setMinimumHeight(36)
    window.check_update_button.clicked.connect(
        lambda: window.check_for_updates(False)
    )
    top_menu.addWidget(window.check_update_button)
    top_menu.addStretch()

    window.developer_tools_panel = QGroupBox("开发者功能")
    developer_menu = QHBoxLayout(window.developer_tools_panel)
    window.automation_home.settings_button.setMinimumHeight(36)
    developer_menu.addWidget(window.automation_home.settings_button)
    window.dtf_accounts_button = QPushButton("DTF 平台账号")
    window.dtf_accounts_button.setMinimumHeight(36)
    window.dtf_accounts_button.clicked.connect(
        lambda: _show_dtf_accounts(window)
    )
    developer_menu.addWidget(window.automation_home.batch_tools)
    developer_menu.addWidget(window.dtf_accounts_button)
    developer_menu.addStretch()
    build_developer_mode(window, top_menu, developer_menu)
    fixed_menu.addLayout(top_menu)
    fixed_menu.addWidget(window.developer_tools_panel)

    department_navigation, department_workspace = build_department_workspace(
        window, window.automation_home
    )
    window.workspace_tabs = QTabWidget()
    workspace_policy = window.workspace_tabs.sizePolicy()
    workspace_policy.setVerticalPolicy(QSizePolicy.Ignored)
    window.workspace_tabs.setSizePolicy(workspace_policy)
    window.department_root_tab_index = window.workspace_tabs.addTab(
        department_workspace, "部门工作区"
    )
    install_machine_status_tab(window, window.workspace_tabs)
    install_production_platform_tab(window, window.workspace_tabs)

    layout = QVBoxLayout()
    window.global_cutter_mode = CutterModeBanner(window)
    window.build_update_status()
    window.global_activity_center = GlobalActivityCenter(window.activity_hub, window)
    layout.addWidget(window.dtf_tools_bar)
    layout.addWidget(window.global_cutter_mode)
    layout.addWidget(department_navigation)
    layout.addWidget(window.global_activity_center)
    layout.addWidget(window.workspace_tabs, 1)
    container = QWidget()
    container.setLayout(layout)
    window.setCentralWidget(container)


def _show_dtf_accounts(window) -> None:
    from ..dtf_accounts import DtfAccountDialog

    DtfAccountDialog(window).exec()
