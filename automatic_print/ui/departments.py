"""Top-level department navigation for isolated print workflows."""

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class Department:
    key: str
    label: str
    state: str


DEPARTMENTS = (
    Department("dtf", "DTF", "existing"),
    Department("uv", "UV", "development"),
    Department("3d", "3D", "placeholder"),
)
DEFAULT_DEPARTMENT = "uv"


def build_department_workspace(window, dtf_workspace):
    """Build one parent selector whose children never share live UI state."""
    navigation = QGroupBox("生产部门")
    row = QHBoxLayout(navigation)
    selector = QComboBox()
    for department in DEPARTMENTS:
        selector.addItem(f"{department.label} 部门", department.key)
    status = QLabel()
    status.setTextInteractionFlags(Qt.TextSelectableByMouse)
    row.addWidget(QLabel("当前部门"))
    row.addWidget(selector)
    row.addWidget(status, 1)

    pages = QStackedWidget()
    page_indexes = {}
    for department in DEPARTMENTS:
        if department.key == "dtf":
            page = dtf_workspace
        elif department.key == "uv":
            page = _uv_workspace(window)
            window.uv_workspace = page
        else:
            page = _placeholder(department)
        page_indexes[department.key] = pages.addWidget(page)

    window.department_selector = selector
    window.department_status = status
    window.department_workspace = pages
    window.department_key = DEFAULT_DEPARTMENT

    saved = window.preferences.value(
        "department/current", DEFAULT_DEPARTMENT, str
    ).strip().casefold()
    if saved not in page_indexes:
        saved = DEFAULT_DEPARTMENT

    def select_department(_index=-1):
        requested = selector.currentData()
        current = window.department_key
        if requested != current and _department_task_active(window, current):
            selector.blockSignals(True)
            selector.setCurrentIndex(max(0, selector.findData(current)))
            selector.blockSignals(False)
            window.status.setText(
                f"{_label(current)} 部门任务仍在运行；任务上下文已保留，未切换部门。"
            )
            return
        department = _department(requested)
        window.department_key = department.key
        pages.setCurrentIndex(page_indexes[department.key])
        window.preferences.setValue("department/current", department.key)
        window.setWindowTitle(f"{department.label} 自动化打印工作台")
        dtf_controls = department.key == "dtf"
        if department.state == "existing":
            status.setText("当前：DTF · 现有自动化打印工作区")
        elif department.state == "development":
            status.setText("当前：UV · uvbranch 独立开发工作区")
        else:
            status.setText("当前：3D · 已建立部门分类，等待对应分支实现")
        sync_dtf_tool_visibility(window)
        sync_download = getattr(
            window, "sync_production_download_visibility", None
        )
        if sync_download is not None:
            sync_download()

    selector.currentIndexChanged.connect(select_department)
    selector.setCurrentIndex(max(0, selector.findData(saved)))
    select_department()
    return navigation, pages


def sync_dtf_tool_visibility(window):
    """Keep the fixed DTF toolbar consistent across department and mode changes."""
    dtf_controls = getattr(window, "department_key", "dtf") == "dtf"
    developer = dtf_controls and bool(
        getattr(window, "developer_mode_enabled", False)
    )
    for control in (
        window.automation_home.settings_button,
        window.dtf_accounts_button,
        window.developer_features_button,
        window.developer_mode_checkbox,
    ):
        control.setEnabled(dtf_controls)
        control.setVisible(dtf_controls)
    window.automation_home.batch_tools.setVisible(developer)
    window.full_test_button.setVisible(developer)
    window.full_test_result.setVisible(developer)


def _placeholder(department):
    page = QWidget()
    layout = QVBoxLayout(page)
    title = QLabel(f"{department.label} 部门")
    title.setStyleSheet("font-size: 24px; font-weight: bold;")
    detail = QLabel(
        f"{department.label} 已作为独立自动化打印部门建立。"
        "当前分支不加载该部门的平台、参数、批次或任务状态。"
    )
    detail.setWordWrap(True)
    detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
    layout.addWidget(title)
    layout.addWidget(detail)
    layout.addStretch()
    return page


def _uv_workspace(window):
    from .uv_workspace import UvWorkspace
    return UvWorkspace(window)


def _department(key):
    return next(item for item in DEPARTMENTS if item.key == key)


def _label(key):
    return _department(key).label


def _department_task_active(window, key):
    """Shared downloads and updates do not belong to either department."""
    if key == "uv":
        return window.uv_workspace.controller.active
    if key != "dtf":
        return False
    automated = getattr(window, "automated_layout_page", None)
    bulk = getattr(window, "bulk_controller", None)
    return any((
        window.layout_generation.active,
        window.automation_home.thread is not None,
        getattr(bulk, "thread", None) is not None,
        bool(automated and automated.busy),
    ))
