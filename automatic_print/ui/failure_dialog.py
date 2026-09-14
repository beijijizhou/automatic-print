"""Scrollable, selectable and explicitly copyable failure diagnostics."""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QApplication


def show_failure_dialog(parent, message):
    dialog = QDialog(parent)
    dialog.setWindowTitle('生成失败 · 订单诊断')
    dialog.resize(780,520)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel('本批未完成结果禁止打印。可复制下方订单、文件及原因进行核查。'))
    details = QPlainTextEdit()
    details.setReadOnly(True)
    details.setPlainText(message)
    layout.addWidget(details)
    buttons = QHBoxLayout()
    copy = QPushButton('复制全部报错详情')
    copy.clicked.connect(lambda: QApplication.clipboard().setText(message))
    close = QPushButton('关闭')
    close.clicked.connect(dialog.accept)
    buttons.addWidget(copy)
    buttons.addStretch()
    buttons.addWidget(close)
    layout.addLayout(buttons)
    dialog.exec()
