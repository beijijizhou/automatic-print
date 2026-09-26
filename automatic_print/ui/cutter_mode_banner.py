"""Persistent production-mode control shown above every workspace tab."""

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class CutterModeBanner(QWidget):
    """Mirror the canonical cutter mode without creating another preference."""

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.cutter = window.cutter_settings
        self.setObjectName("cutterModeBanner")
        self.window = window
        self.title = QLabel("当前生产信息")
        self.title.setObjectName("cutterModeTitle")
        self.mode_label = QLabel("生产模式")
        self.mode = QComboBox()
        self.mode.setMinimumWidth(220)
        self.mode.setAccessibleName("当前生产模式")
        self.mode.setToolTip(
            "这里是生产模式的唯一入口：正常排版不生成刀码；"
            "强制单列和自动多列会生成切膜刀码。"
        )
        self.production = QLabel()
        self.production.setObjectName("productionInfoSummary")
        self.status = QLabel()
        self.status.setWordWrap(True)

        details = QVBoxLayout()
        details.setContentsMargins(0, 0, 0, 0)
        details.setSpacing(2)
        details.addWidget(self.production)
        details.addWidget(self.status)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addWidget(self.mode_label)
        layout.addWidget(self.mode)
        layout.addLayout(details, 1)

        self.mode.currentIndexChanged.connect(self._mode_requested)
        self.cutter.mode.currentIndexChanged.connect(self.refresh)
        self.cutter.film.currentIndexChanged.connect(self.refresh)
        self.cutter.custom_film.value.valueChanged.connect(self.refresh)
        self.cutter.printable.left.valueChanged.connect(self.refresh)
        self.cutter.printable.right.valueChanged.connect(self.refresh)
        self.cutter.printable.output_width.valueChanged.connect(self.refresh)
        window.label_settings.machine.currentIndexChanged.connect(self.refresh)
        window.label_settings.platform.currentTextChanged.connect(self.refresh)
        self.refresh()

    def refresh(self, *_args):
        current = self.cutter.mode.currentData()
        values = [self.cutter.mode.itemData(i)
                  for i in range(self.cutter.mode.count())]
        if values != [self.mode.itemData(i) for i in range(self.mode.count())]:
            self.mode.blockSignals(True)
            self.mode.clear()
            for index in range(self.cutter.mode.count()):
                self.mode.addItem(
                    self.cutter.mode.itemText(index),
                    self.cutter.mode.itemData(index),
                )
            self.mode.blockSignals(False)
        self.mode.blockSignals(True)
        self.mode.setCurrentIndex(self.mode.findData(current))
        self.mode.blockSignals(False)
        machine = self.window.label_settings.machine.currentData()
        platform = self.window.label_settings.platform.currentText().strip() or "未选择平台"
        self.production.setText(
            f"机器 {machine}　·　平台 {platform}　·　"
            f"{self.cutter.film.currentText()}　·　"
            f"有效画布 {self.cutter.printable.usable_width():g} 毫米"
        )
        cutting = current != "free"
        self.setProperty("cuttingMode", cutting)
        if cutting:
            self.status.setText(
                f"{self.cutter.mode.currentText()}：会生成刀码并应用刀位；"
                "开始排版前请确认膜规格与刀位。"
            )
            background, foreground, border = "#fff7ed", "#9a3412", "#f97316"
        else:
            self.status.setText("正常排版（无刀码）：不会生成切膜刀码。")
            background, foreground, border = "#ecfdf5", "#166534", "#22c55e"
        self.setStyleSheet(
            f"QWidget#cutterModeBanner {{ background:{background};"
            f"color:{foreground};border:3px solid {border};border-radius:8px; }}"
            f"QWidget#cutterModeBanner QLabel {{ color:{foreground};border:none; }}"
            "QLabel#cutterModeTitle { font-size:16px;font-weight:800; }"
            "QLabel#productionInfoSummary { font-weight:700; }"
        )

    def _mode_requested(self, index):
        if index < 0:
            return
        target = self.cutter.mode.findData(self.mode.itemData(index))
        if target >= 0:
            self.cutter.mode.setCurrentIndex(target)
