"""Editable current-film identity backed by canonical print settings."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class CurrentFilmLabel(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.cutter = window.cutter_settings
        self.setObjectName("currentFilm")
        self.setMinimumWidth(360)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
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

        edits = QVBoxLayout()
        edits.setContentsMargins(0, 0, 0, 0)
        film_row = QHBoxLayout()
        film_row.addWidget(QLabel("膜规格"))
        film_row.addWidget(self.film)
        film_row.addWidget(self.custom_width)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("排版"))
        mode_row.addWidget(self.mode)
        edits.addLayout(film_row)
        edits.addLayout(mode_row)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.addWidget(self.summary, 1)
        layout.addLayout(edits)

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
        modes = {
            "single": "单列切膜",
            "dual": "自动多列切膜",
            "free": "正常排版（无刀码）",
        }
        mode = modes.get(
            self.cutter.mode.currentData(), "待选择排版模式"
        )
        self.summary.setText(
            f"当前选用膜：{film / 10:g} 厘米\n"
            f"可打印 {usable:g} 毫米 · {mode}"
        )
        self.setToolTip(
            "当前打印参数，不是自动选用面积最省方案。\n"
            f"物理膜宽 {film:g} 毫米 − RIIN左预留 "
            f"{self.cutter.printable.left.value():g} 毫米 − 右预留 "
            f"{self.cutter.printable.right.value():g} 毫米。"
        )
        invalid = usable <= 0
        background = "#fee2e2" if invalid else "#fff7ed"
        foreground = "#991b1b" if invalid else "#9a3412"
        border = "#ef4444" if invalid else "#fb923c"
        self.setStyleSheet(
            f"QWidget#currentFilm {{ background:{background};"
            f"border:2px solid {border};border-radius:7px; }}"
            f"QWidget#currentFilm QLabel {{ color:{foreground};border:none; }}"
            "QWidget#currentFilm QLabel:first-child { font-size:17px;"
            "font-weight:bold; }"
        )
        if invalid:
            self.summary.setText(self.summary.text() + "\n预留超过膜宽，禁止生成")

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
