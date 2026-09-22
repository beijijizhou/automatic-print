"""DTF platform account status without exposing provider credentials."""

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog, QHeaderView, QHBoxLayout, QLabel, QPushButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout,
)


class AccountWorker(QObject):
    finished = Signal(object)

    def __init__(self, platform=None):
        super().__init__()
        self.platform = platform

    @Slot()
    def run(self):
        try:
            from ..automation.api.dtf_accounts import account_status, probe_account
            result = (probe_account(self.platform) if self.platform
                      else account_status())
            self.finished.emit({"platform": self.platform, "result": result})
        except Exception as error:
            self.finished.emit({"platform": self.platform, "error": str(error)})


class DtfAccountDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DTF 平台账号")
        self.resize(720, 500)
        self.thread = None
        self.worker = None
        self.pending_close = False
        layout = QVBoxLayout(self)
        self.summary = QLabel("正在读取服务端账号状态…")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.table = QTreeWidget()
        self.table.setHeaderLabels(("平台", "服务端配置", "登录验证"))
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.header().setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        self.refresh_button = QPushButton("刷新账号状态")
        self.verify_button = QPushButton("验证选中平台登录")
        self.verify_button.setEnabled(False)
        self.close_button = QPushButton("关闭")
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.verify_button)
        actions.addStretch()
        actions.addWidget(self.close_button)
        layout.addLayout(actions)
        self.refresh_button.clicked.connect(lambda: self._start())
        self.verify_button.clicked.connect(self._verify_selected)
        self.close_button.clicked.connect(self.reject)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self._start()

    def _start(self, platform=None):
        if self.thread is not None:
            return
        self.refresh_button.setEnabled(False)
        self.verify_button.setEnabled(False)
        self.summary.setText(
            f"正在验证 {platform} 登录…" if platform else "正在读取服务端账号状态…")
        self.thread = QThread(self)
        self.worker = AccountWorker(platform)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._received)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._thread_stopped)
        self.thread.start()

    def _verify_selected(self):
        selected = self.table.selectedItems()
        if selected:
            self._start(selected[0].text(0))

    @Slot()
    def _selection_changed(self):
        selected = self.table.selectedItems()
        self.verify_button.setEnabled(
            bool(selected) and self.thread is None and
            selected[0].data(0, Qt.UserRole) == "server_login")

    @Slot(object)
    def _received(self, payload):
        if self.pending_close:
            return
        error = payload.get("error")
        platform = payload.get("platform")
        if platform:
            item = next((self.table.topLevelItem(index)
                         for index in range(self.table.topLevelItemCount())
                         if self.table.topLevelItem(index).text(0) == platform), None)
            if item is not None:
                item.setText(2, "验证失败" if error else "登录已验证")
                item.setToolTip(2, error or "服务端登录成功；未读取订单或下载文件。")
            self.summary.setText(
                f"{platform} 登录验证失败：{error}" if error else
                f"{platform} 服务端登录已验证。")
            return
        if error:
            self.summary.setText(f"账号状态读取失败：{error}")
            return
        rows = payload["result"]
        self.table.clear()
        for row in rows:
            state = "已配置" if row["configured"] else "待配置"
            mode = "独立服务" if row["mode"] == "dedicated_gateway" else (
                "网页令牌" if row["mode"] == "browser_token" else "服务端登录")
            verification = (
                "未验证" if row["mode"] == "server_login" else
                "在 S2B 下载页验证" if row["mode"] == "dedicated_gateway" else
                "需网页会话验证")
            item = QTreeWidgetItem((row["platform"], f"{state} · {mode}", verification))
            item.setFlags(item.flags() | Qt.ItemIsSelectable)
            item.setData(0, Qt.UserRole, row["mode"])
            self.table.addTopLevelItem(item)
        self.summary.setText(
            f"已同步 {sum(bool(row['configured']) for row in rows)}/{len(rows)} 个 DTF 平台账号。"
            "“已配置”不代表登录仍有效；服务端登录平台可选中验证。")

    @Slot()
    def _thread_stopped(self):
        self.thread = None
        self.worker = None
        if self.pending_close:
            super().reject()
            return
        self.refresh_button.setEnabled(True)
        self._selection_changed()

    def reject(self):
        if self.thread is not None:
            self.pending_close = True
            self.summary.setText("正在完成当前只读账号检查，随后关闭窗口…")
            return
        super().reject()
