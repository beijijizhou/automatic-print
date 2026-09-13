from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QWidget


class CutterSettingsPanel(QWidget):
    """Film specification owns its valid production modes and knife settings."""

    def __init__(self, preferences, width, rotation, direction, parent=None, block=None):
        super().__init__(parent)
        self.preferences = preferences
        self.block = block
        self.width_control, self.rotation, self.direction = width, rotation, direction
        self.film = QComboBox()
        self.film.addItem("45 厘米膜", 450)
        self.film.addItem("60 厘米膜", 600)
        self.mode = QComboBox()
        self.knife = self._box(300, 1, 599)
        self.auto_knife = QCheckBox("按整批图片自动计算统一刀位")
        self.auto_knife.setChecked(preferences.value("cutter/auto_knife", True, bool))
        self.rotation_zone = QCheckBox("省膜时启用独立旋转区（每行一张，换刀一次）")
        self.rotation_zone.setChecked(preferences.value("cutter/rotation_zone", True, bool))
        self.safety = self._box(3, 0.1, 30)
        self.marker_offset = self._box(0, 0, 100)
        note = QLabel(
            "先选择膜规格，再选择排版模式。固定双列的刀位整批不变；"
            "右侧色块左边缘 = 刀位 + 安全距离 + 色块偏移。"
            "常规区保持固定刀位；旋转区每行一张，完整订单迁移。图片必须有可靠 DPI。"
        )
        note.setWordWrap(True)
        form = QFormLayout(self)
        for text, control in (
            ("膜规格", self.film), ("生产排版模式", self.mode),
            ("刀位选择", self.auto_knife),
            ("旋转区域", self.rotation_zone),
            ("刀位距膜左边（毫米）", self.knife),
            ("刀位两侧安全距离（毫米）", self.safety),
            ("右侧色块基准偏移（毫米）", self.marker_offset), ("", note),
        ):
            form.addRow(text, control)
        previous_width = int(width.value())
        default_film = previous_width if previous_width in {450, 600} else 600
        film = preferences.value("cutter/film_mm", default_film, int)
        self.film.setCurrentIndex(max(0, self.film.findData(film)))
        self._initializing = True
        self._film_changed()
        mode = preferences.value("cutter/mode", self.mode.currentData(), str)
        self.mode.setCurrentIndex(max(0, self.mode.findData(mode)))
        for control, key, default in (
            (self.knife, "knife_mm", self.film.currentData() / 2),
            (self.safety, "safety_mm", 3),
            (self.marker_offset, "marker_offset_mm", 0),
        ):
            control.setValue(preferences.value("cutter/" + key, default, float))
        self._initializing = False
        self.film.currentIndexChanged.connect(self._film_changed)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.auto_knife.toggled.connect(self._mode_changed)
        self._mode_changed()

    def _film_changed(self, *_args):
        film = self.film.currentData()
        self.width_control.setValue(film)
        self.mode.blockSignals(True)
        self.mode.clear()
        modes = (
            [("单列切膜（默认）", "single"), ("固定双列切膜（小图）", "dual")]
            if film == 450 else
            [("固定双列切膜（默认）", "dual"), ("单列切膜", "single")]
        )
        for text, value in modes + [("自由排版（不使用固定刀位）", "free")]:
            self.mode.addItem(text, value)
        self.mode.blockSignals(False)
        self.knife.setMaximum(film - 1)
        self.knife.setValue(film / 2)
        self._mode_changed()

    def _mode_changed(self, *_args):
        if getattr(self, "_initializing", False):
            return
        mode = self.mode.currentData()
        for control in (self.knife, self.safety, self.marker_offset):
            control.setEnabled(mode == "dual")
        self.auto_knife.setEnabled(mode == "dual")
        self.rotation_zone.setEnabled(mode == "dual")
        self.knife.setEnabled(mode == "dual" and not self.auto_knife.isChecked())
        self.rotation.setEnabled(mode == "free")
        self.direction.setEnabled(mode == "free")
        if mode != "free":
            self.rotation.setChecked(False)
        if self.block is not None:
            for control in (self.block.enabled, self.block.position, self.block.offset_y):
                control.setEnabled(mode == "free")
            if mode != "free":
                self.block.enabled.setChecked(True)
                self.block.position.setCurrentIndex(self.block.position.findData("left_top"))
                self.block.offset_y.setValue(0)

    def save(self):
        for key, value in {
            "film_mm": self.film.currentData(), "mode": self.mode.currentData(),
            "auto_knife": self.auto_knife.isChecked(),
            "rotation_zone": self.rotation_zone.isChecked(),
            "knife_mm": self.knife.value(), "safety_mm": self.safety.value(),
            "marker_offset_mm": self.marker_offset.value(),
        }.items():
            self.preferences.setValue("cutter/" + key, value)

    @staticmethod
    def _box(value, minimum, maximum):
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setDecimals(1)
        box.setValue(value)
        return box
