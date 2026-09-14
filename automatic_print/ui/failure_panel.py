"""Dedicated, copyable diagnostics, kept outside normal production data."""
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton, QApplication


class FailurePanel(QGroupBox):
    def __init__(self,parent=None):
        super().__init__('报错诊断 · 未完成结果禁止打印',parent)
        self.setStyleSheet('FailurePanel { border: 2px solid #ef4444; border-radius: 7px; '
                          'background: #fff1f2; margin-top: 12px; padding: 10px; }')
        self.details=QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(180)
        self.details.setMaximumHeight(320)
        self.copy_button=QPushButton('一键复制报错信息')
        self.copy_button.setStyleSheet('background: #dc2626; color: white; padding: 8px; font-weight: bold;')
        self.copy_button.clicked.connect(self.copy_all)
        self.open_button=QPushButton('放大查看报错详情')
        self.open_button.clicked.connect(self.open_details)
        buttons=QHBoxLayout()
        buttons.addWidget(self.copy_button)
        buttons.addWidget(self.open_button)
        buttons.addStretch()
        layout=QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addWidget(self.details)
        self.hide()

    def show_message(self,message):
        self.details.setPlainText(message)
        self.show()

    def reset(self):
        self.details.clear()
        self.hide()

    def copy_all(self):
        QApplication.clipboard().setText(self.details.toPlainText())

    def open_details(self):
        from .failure_dialog import show_failure_dialog
        show_failure_dialog(self,self.details.toPlainText())
