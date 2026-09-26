"""Visible log surface for developer full-test runs."""

from PySide6.QtWidgets import QDialog, QLabel, QPlainTextEdit, QVBoxLayout


class FullTestLogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("开发者 · 完整测试结果")
        self.resize(880, 560)
        note = QLabel(
            "依次运行完整自动测试和本机真实生产样本回归。自动测试逐项显示文件、测试名称"
            "与通过/失败状态；真实回归覆盖 Haloo、隆丰、莆田和 S2B，只生成测试 PNG 与"
            "核验报告，不生成、装载或发送 PRN。"
        )
        note.setWordWrap(True)
        self.status = QLabel("尚未运行")
        self.status.setWordWrap(True)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout = QVBoxLayout(self)
        layout.addWidget(note)
        layout.addWidget(self.status)
        layout.addWidget(self.log, 1)

    def closeEvent(self, event):
        controller = getattr(self.parent(), "full_test_controller", None)
        if controller and controller.is_running():
            self.hide()
            event.ignore()
            return
        super().closeEvent(event)
