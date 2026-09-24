"""Visible, persistent controls for customer-selected batch grouping rules."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QGridLayout, QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from ....automation.batches.supplements.grouping.strategy import (
    GroupingStrategy,
    default_strategy,
)


FIELDS = (
    ("by_composition", "按订单组成"),
    ("by_logistics", "按物流"),
    ("by_face", "按单双面（单项单件）"),
    ("by_color", "按颜色（单面单项单件）"),
    ("by_size", "按尺码档（单面单项单件）"),
    ("by_style", "按底款（单项单件）"),
)


class StrategyEditor(QGroupBox):
    changed = Signal()

    def __init__(self, platform_name: str, settings=None, parent=None):
        super().__init__("批次分组规则（可自行组合）", parent)
        self.platform_name = platform_name
        self.settings = settings
        self.controls = {}
        layout = QVBoxLayout(self)
        intro = QLabel(_platform_explanation(platform_name))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        row = QWidget()
        grid = QGridLayout(row)
        defaults = default_strategy(platform_name)
        for index, (field, text) in enumerate(FIELDS):
            control = QCheckBox(text)
            default = getattr(defaults, field)
            control.setChecked(self._read(field, default))
            control.toggled.connect(self._selection_changed)
            self.controls[field] = control
            grid.addWidget(control, index // 2, index % 2)
        layout.addWidget(row)

        footer = QWidget()
        footer_layout = QGridLayout(footer)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        reset = QPushButton("恢复平台默认规则")
        reset.clicked.connect(self.reset_defaults)
        footer_layout.addWidget(self.summary, 0, 0)
        footer_layout.addWidget(reset, 0, 1)
        layout.addWidget(footer)
        self._refresh_summary()

    def strategy(self) -> GroupingStrategy:
        return GroupingStrategy(
            by_logistics=self.controls["by_logistics"].isChecked(),
            by_face=self.controls["by_face"].isChecked(),
            by_color=self.controls["by_color"].isChecked(),
            by_size=self.controls["by_size"].isChecked(),
            by_style=self.controls["by_style"].isChecked(),
            by_composition=self.controls["by_composition"].isChecked(),
        )

    def reset_defaults(self) -> None:
        defaults = default_strategy(self.platform_name)
        for field, control in self.controls.items():
            control.blockSignals(True)
            control.setChecked(getattr(defaults, field))
            control.blockSignals(False)
        self._selection_changed()

    def _read(self, field: str, default: bool) -> bool:
        if self.settings is None:
            return default
        return self.settings.value(self._key(field), default, bool)

    def _selection_changed(self, *_args) -> None:
        if self.settings is not None:
            for field, control in self.controls.items():
                self.settings.setValue(self._key(field), control.isChecked())
        self._refresh_summary()
        self.changed.emit()

    def _refresh_summary(self) -> None:
        labels = " + ".join(self.strategy().enabled_labels()) or "不额外拆分"
        self.summary.setText(f"当前实际组合：{labels}。整单始终保持在同一分组。")

    def _key(self, field: str) -> str:
        return f"batch_strategy/{self.platform_name}/{field}"


def _platform_explanation(platform_name: str) -> str:
    if platform_name == "隆丰":
        return (
            "已确认默认规则：只纳入 A00 默认工艺；多件按订单组成；单项单件分单双面，"
            "单面再按实际颜色。默认不按物流、底款或尺码。下方可修改组合。"
        )
    if platform_name == "Haloo":
        return (
            "已确认默认规则：按物流和订单组成；单项单件分单双面；单面分黑色、白色和"
            "其他颜色混色，黑白再分 S–XL 与 2XL–5XL。默认不按底款。下方可修改组合。"
        )
    if platform_name == "S2B":
        return (
            "已确认默认规则：不按物流，先按订单组成；单项单件分单双面；单面分黑色、"
            "白色和其他颜色混色，黑白再分 S–XL 与 2XL–5XL。默认不按底款。"
            "下方仍可自行修改组合。"
        )
    return (
        "平台默认按物流、订单组成、单双面、颜色、尺码档和底款分组。"
        "下方可修改组合；多件订单始终保持整单。"
    )
