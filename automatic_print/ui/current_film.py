"""Editable current-film identity backed by canonical print settings."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QWidget,
)


class CurrentFilmLabel(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.cutter = window.cutter_settings
        self.setObjectName("currentFilm")
        self.setMinimumWidth(500)
        self.summary = QLabel()
        self.summary.setTextFormat(Qt.PlainText)
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.film = QComboBox()
        self.mode = QComboBox()
        self.custom_width = QDoubleSpinBox()
        self.custom_width.setRange(5, 500)
        self.custom_width.setDecimals(2)
        self.custom_width.setSingleStep(0.5)
        self.custom_width.setSuffix(" 厘米")
        self._copy_items(self.cutter.film, self.film)
        self._copy_items(self.cutter.mode, self.mode)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        layout.addWidget(QLabel("膜规格"))
        layout.addWidget(self.film)
        layout.addWidget(self.custom_width)
        layout.addWidget(QLabel("排版"))
        layout.addWidget(self.mode, 1)
        layout.addWidget(self.summary)

        self.film.currentIndexChanged.connect(self._film_requested)
        self.mode.currentIndexChanged.connect(self._mode_requested)
        self.custom_width.valueChanged.connect(self._custom_requested)
        for signal in (
            self.cutter.film.currentIndexChanged,
            self.cutter.mode.currentIndexChanged,
            self.cutter.width_control.valueChanged,
            self.cutter.custom_film.value.valueChanged,
            self.cutter.printable.left.valueChanged,
            self.cutter.printable.right.valueChanged,
        ):
            signal.connect(self.refresh)
        self.refresh()

    def text(self) -> str:
        return self.summary.text()

    def textInteractionFlags(self):
        return self.summary.textInteractionFlags()

    def refresh(self, *_args):
        self._sync_controls()
        film = self.cutter.width_control.value()
        usable = self.cutter.printable.usable_width()
        self.summary.setText(f"可打印宽度：{usable:g} 毫米")
        self.setToolTip(
            "当前打印参数，不是自动选用面积最省方案。\n"
            f"物理膜宽 {film:g} 毫米 − RIIN左预留 "
            f"{self.cutter.printable.left.value():g} 毫米 − 右预留 "
            f"{self.cutter.printable.right.value():g} 毫米。"
        )
        invalid = usable <= 0
        background = "#fee2e2" if invalid else "#f8fafc"
        foreground = "#991b1b" if invalid else "#64748b"
        border = "#ef4444" if invalid else "#dce4ef"
        self.setStyleSheet(
            f"QWidget#currentFilm {{ background:{background};"
            f"border:1px solid {border};border-radius:7px; }}"
            f"QWidget#currentFilm QLabel {{ color:{foreground};border:none; }}"
        )
        if invalid:
            self.summary.setText("预留超过膜宽，禁止生成")

    def _sync_controls(self) -> None:
        self._copy_items(self.cutter.mode, self.mode)
        self.film.blockSignals(True)
        self.film.setCurrentIndex(self.cutter.film.currentIndex())
        self.film.blockSignals(False)
        self.mode.blockSignals(True)
        self.mode.setCurrentIndex(self.cutter.mode.currentIndex())
        self.mode.blockSignals(False)
        self.custom_width.blockSignals(True)
        self.custom_width.setValue(self.cutter.custom_film.value.value())
        self.custom_width.blockSignals(False)
        self.custom_width.setVisible(
            self.cutter.film.currentData() == "custom"
        )

    def _film_requested(self, index: int) -> None:
        if index >= 0:
            self.cutter.film.setCurrentIndex(index)

    def _mode_requested(self, index: int) -> None:
        if index >= 0:
            self.cutter.mode.setCurrentIndex(index)

    def _custom_requested(self, value: float) -> None:
        self.cutter.custom_film.value.setValue(value)

    @staticmethod
    def _copy_items(source: QComboBox, target: QComboBox) -> None:
        current = target.currentData()
        values = [source.itemData(index) for index in range(source.count())]
        if values == [target.itemData(i) for i in range(target.count())]:
            return
        target.blockSignals(True)
        target.clear()
        for index in range(source.count()):
            target.addItem(source.itemText(index), source.itemData(index))
        restored = target.findData(current)
        target.setCurrentIndex(restored if restored >= 0 else 0)
        target.blockSignals(False)
