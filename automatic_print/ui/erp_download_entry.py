"""Developer-only workspace for generated ERP production batches."""

from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..automation.providers.registry import ERP_PLATFORMS
from ..batch_ui.dialog import AutomationDialog
from .developer_mode import bind_developer_tab_visibility


PLATFORM_ORDER = ("隆丰", "莆田", "S2B", "Haloo")


class ProductionPlatformDownloadPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__(window)
        self.host_window = window
        self.workbenches: dict[str, AutomationDialog] = {}
        self.platform_tabs = QTabWidget()
        self.empty = QLabel("请至少选择一个需要读取的生产平台。")
        self.empty.setStyleSheet("padding:24px;color:#667085;")
        self.platform_checks: dict[str, QCheckBox] = {}

        choices = QGroupBox("生产平台（可多选）")
        choice_row = QHBoxLayout(choices)
        for name in PLATFORM_ORDER:
            if name not in ERP_PLATFORMS and name != "S2B":
                continue
            checkbox = QCheckBox(name)
            checkbox.toggled.connect(
                lambda checked, platform=name: self._toggle_platform(
                    platform, checked
                )
            )
            self.platform_checks[name] = checkbox
            choice_row.addWidget(checkbox)
        choice_row.addStretch()

        intro = QLabel(
            "每个平台独立保存登录、批次列表、下载进度和日志。"
            "当前只下载并解压已生成批次，不会自动启动排版。"
        )
        intro.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(choices)
        layout.addWidget(self.empty)
        layout.addWidget(self.platform_tabs, 1)
        self.platform_tabs.hide()
        self.platform_checks["隆丰"].setChecked(True)

    @property
    def thread(self):
        return next(
            (
                workbench.thread
                for workbench in self.workbenches.values()
                if workbench.thread is not None
            ),
            None,
        )

    def _toggle_platform(self, name: str, checked: bool) -> None:
        workbench = self.workbenches.get(name)
        if checked and workbench is None:
            workbench = AutomationDialog(
                self.host_window,
                local_only=False,
                platform_names=(name,),
                download_only=True,
            )
            self.workbenches[name] = workbench
        if checked:
            if self.platform_tabs.indexOf(workbench) < 0:
                self.platform_tabs.addTab(workbench, name)
            self.platform_tabs.setCurrentWidget(workbench)
        elif workbench is not None:
            index = self.platform_tabs.indexOf(workbench)
            if index >= 0:
                self.platform_tabs.removeTab(index)
        has_platform = self.platform_tabs.count() > 0
        self.empty.setVisible(not has_platform)
        self.platform_tabs.setVisible(has_platform)


def install_production_platform_tab(
    window, tabs: QTabWidget
) -> ProductionPlatformDownloadPage:
    page = ProductionPlatformDownloadPage(window)
    index = tabs.addTab(page, "生产平台下载")
    tabs.setTabToolTip(
        index,
        "从一个或多个生产平台读取并下载已经生成的生产批次。",
    )

    bind_developer_tab_visibility(window, tabs, page, index)
    window.production_platform_download_page = page
    window.production_platform_tab_index = index
    window.longfeng_erp_dialog = page  # Active-task compatibility.
    return page
