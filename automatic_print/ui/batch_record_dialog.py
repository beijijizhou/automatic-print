"""Read-only details for the batch selected on the shared status board."""

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout


class BatchRecordDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('批次记录')
        self.resize(760, 520)
        layout = QVBoxLayout(self)
        self.details = QPlainTextEdit(self)
        self.details.setReadOnly(True)
        layout.addWidget(self.details)
        actions = QHBoxLayout()
        actions.addStretch()
        copy = QPushButton('复制记录')
        copy.clicked.connect(self.copy_record)
        actions.addWidget(copy)
        layout.addLayout(actions)

    def show_record(self, title, text):
        self.setWindowTitle(f'批次记录 · {title}')
        self.details.setPlainText(text)
        self.details.moveCursor(QTextCursor.Start)
        self.show()
        self.raise_()
        self.activateWindow()

    def copy_record(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.details.toPlainText())
