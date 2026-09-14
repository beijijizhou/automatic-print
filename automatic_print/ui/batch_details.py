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

    def open_history(self):
        if not getattr(self.parent(), 'developer_mode_enabled', False):
            return
        if not hasattr(self, 'history_page'):
            from .film_history import FilmHistoryPage
            self.history_page = FilmHistoryPage(self)
            self.tabs.addTab(self.history_page, '用膜历史记录')
        self.tabs.setCurrentWidget(self.history_page)
        self.open_details()
        self.history_page.refresh()

    def open_bulk_analysis(self):
        if not getattr(self.parent(), 'developer_mode_enabled', False):
            return
        if not hasattr(self, 'bulk_dialog'):
            from .bulk_film_analysis import BulkFilmAnalysisDialog
            self.bulk_dialog = BulkFilmAnalysisDialog(self.parent())
        self.bulk_dialog.show()
        self.bulk_dialog.raise_()

    def open_bulk_generation(self):
        if self.parent().has_active_tasks():
            return
        if not hasattr(self, 'production_bulk_dialog'):
            from .bulk_generation import BulkGenerationDialog
            self.production_bulk_dialog = BulkGenerationDialog(self.parent())
        self.production_bulk_dialog.show()
        self.production_bulk_dialog.raise_()
