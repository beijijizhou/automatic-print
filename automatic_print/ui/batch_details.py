"""Occasional batch inspection tools, separate from the production workbench."""
from PySide6.QtWidgets import QDialog, QTabWidget, QVBoxLayout, QWidget


class BatchDetailsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('批次详情与检查')
        self.resize(900, 650)
        self.tabs = QTabWidget(self)
        QVBoxLayout(self).addWidget(self.tabs)

    def add_page(self, title, widgets):
        page = QWidget()
        layout = QVBoxLayout(page)
        for widget in widgets:
            layout.addWidget(widget)
        self.tabs.addTab(page, title)

    def open_details(self):
        self.show()
        self.raise_()
        self.activateWindow()
