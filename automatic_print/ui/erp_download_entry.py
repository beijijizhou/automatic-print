"""Shared workspace for generated production batches."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..automation.providers.registry import ERP_PLATFORMS
from ..batch_ui.dialog import AutomationDialog
PLATFORM_ORDER = ("亿点万象", "隆丰", "莆田", "S2B", "Haloo")


class ProductionPlatformDownloadPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__(window)
        self.host_window = window
        self.workbenches: dict[str, QWidget] = {}
        self.platform_tabs = QTabWidget()
        self.platform_tabs.tabBar().hide()
        self.empty = QLabel(
            "尚未选择生产平台\n\n请从上方下拉菜单选择一个平台，"
            "再读取和下载该平台的生产批次。"
        )
        self.empty.setWordWrap(True)
        self.empty.setStyleSheet(
            "padding:48px;border:1px dashed #98a2b3;border-radius:8px;"
            "background:#f8fafc;color:#475467;font-size:16px;"
        )
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setMinimumHeight(180)
        self.platform_selector = QComboBox()
        self.platform_selector.setMinimumWidth(260)
        self.platform_selector.addItem("请选择生产平台…", None)

        choices = QGroupBox("生产平台")
        choice_row = QHBoxLayout(choices)
        choice_row.addWidget(QLabel("当前平台"))
        choice_row.addWidget(self.platform_selector)
        for name in PLATFORM_ORDER:
            if name not in ERP_PLATFORMS and name not in ("S2B", "亿点万象"):
                continue
            self.platform_selector.addItem(name, name)
        choice_row.addStretch()
        self.platform_selector.currentIndexChanged.connect(self._platform_changed)

        intro = QLabel(
            "一次只操作一个生产平台；切换后仍保留各平台已读取的列表和日志。"
            "下载已生成批次后，蜂鸟平台可由用户选择继续本地排版、"
            "PRN生成和PrinterExp加载；亿点万象下载与UV排版分开进行。"
            "自动流程不会启动物理打印。"
        )
        intro.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(choices)
        layout.addWidget(self.empty)
        layout.addWidget(self.platform_tabs, 1)
        self.platform_tabs.hide()

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

    def select_platform(self, name: str | None) -> None:
        index = self.platform_selector.findData(name)
        if index < 0:
            raise ValueError(f"未知生产平台：{name}")
        self.platform_selector.setCurrentIndex(index)

    def _platform_changed(self, _index: int) -> None:
        name = self.platform_selector.currentData()
        while self.platform_tabs.count():
            self.platform_tabs.removeTab(0)
        if not name:
            self.empty.show()
            self.platform_tabs.hide()
            return
        workbench = self.workbenches.get(name)
        if workbench is None:
            if name == "亿点万象":
                from .ydwx_download import YdwxDownloadPage
                workbench = YdwxDownloadPage(self.host_window)
                workbench.idle.connect(
                    lambda: self.host_window.sync_production_download_visibility()
                )
            else:
                workbench = AutomationDialog(
                    self.host_window,
                    local_only=False,
                    platform_names=(name,),
                    download_only=True,
                )
            self.workbenches[name] = workbench
        self.platform_tabs.addTab(workbench, name)
        self.empty.hide()
        self.platform_tabs.show()


def install_production_platform_tab(
    window, tabs: QTabWidget
) -> ProductionPlatformDownloadPage:
    page = ProductionPlatformDownloadPage(window)
    index = tabs.addTab(page, "生产平台下载")
    tabs.setTabToolTip(
        index,
        "从生产平台选择批次，仅下载或继续自动排版并生成PRN。",
    )

    def sync_visibility(*_args):
        uv_selected = getattr(window, "department_key", "dtf") == "uv"
        ydwx = page.workbenches.get("亿点万象")
        if uv_selected:
            page.select_platform("亿点万象")
        elif (ydwx is None or ydwx.thread is None) \
                and page.platform_selector.currentData() == "亿点万象":
            page.select_platform(None)
        visible = (
            getattr(window, "department_key", "dtf") in {"dtf", "uv"}
            or bool(ydwx and ydwx.thread is not None)
        )
        if not visible and tabs.currentWidget() is page:
            tabs.setCurrentIndex(window.department_root_tab_index)
        tabs.setTabVisible(index, visible)

    window.developer_mode_checkbox.toggled.connect(sync_visibility)
    window.sync_production_download_visibility = sync_visibility
    sync_visibility()
    window.production_platform_download_page = page
    window.production_platform_tab_index = index
    window.longfeng_erp_dialog = page  # Active-task compatibility.
    return page
