"""Developer-only history and diagnostic tools."""
from PySide6.QtWidgets import QDialog, QTabWidget, QVBoxLayout


class BatchDetailsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('开发者工具')
        self.resize(900, 650)
        self.tabs = QTabWidget(self)
        QVBoxLayout(self).addWidget(self.tabs)

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
            self.tabs.addTab(self.history_page, '排版历史')
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
        from .bulk_workbench import open_bulk
        open_bulk(self.parent())

    def open_algorithm_costs(self):
        if not getattr(self.parent(), 'developer_mode_enabled', False):
            return
        if not hasattr(self, 'algorithm_page'):
            from .algorithm_costs import AlgorithmCostsPage
            self.algorithm_page = AlgorithmCostsPage(self.parent(), self)
            self.tabs.addTab(self.algorithm_page, '算法开销')
        self.algorithm_page.refresh()
        self.tabs.setCurrentWidget(self.algorithm_page)
        self.open_details()
