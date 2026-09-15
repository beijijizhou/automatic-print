from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QWidget
from .printable_width import PrintableWidthPanel
from .transition_settings import TransitionSettings


class CutterSettingsPanel(QWidget):
    """Film specification owns its valid production modes and knife settings."""

    def __init__(self, preferences, width, rotation, direction, parent=None, block=None):
        super().__init__(parent)
        self.preferences = preferences
        self.quick_mode = QCheckBox('上线快速模式（不做全批旋转搜索，读取与排版一次完成）')
        self.quick_mode.setChecked(preferences.value('cutter/quick_mode', True, bool))
        self.block = block
        self.width_control, self.rotation, self.direction = width, rotation, direction
        self.film = QComboBox()
        self.film.addItem("45 厘米膜", 450)
        self.film.addItem("60 厘米膜", 600)
        self.film.addItem('自定义膜宽', 'custom')
        from .custom_film import CustomFilmWidth
        self.custom_film = CustomFilmWidth(preferences,self)
        self.mode = QComboBox()
        self.knife = self._box(300, 1, 599)
        self.printable = PrintableWidthPanel(preferences, width, self.knife, self)
        self.auto_knife = QCheckBox("按整批图片自动计算统一刀位")
        self.auto_knife.setChecked(preferences.value("cutter/auto_knife", True, bool))
        self.rotation_zone = QCheckBox("省膜时启用独立旋转区（每行一张，换刀一次）")
        self.rotation_zone.setChecked(not self.quick_mode.isChecked() and preferences.value("cutter/rotation_zone", False, bool))
        self.two_zone = QCheckBox('贪心双排集中：能安全双排的订单优先双排，其余进入旋转区')
        legacy = preferences.value('developer/majority_two_zone', True, bool)
        self.two_zone.setChecked(preferences.value('layout/majority_two_zone', legacy, bool))
        self.two_zone.setToolTip('能安全双排的完整订单优先集中双排，其余进入旋转区；最多两个区域。')
        self.force_small_pair = QCheckBox('强行 S–L 双排（宽度超过 270 毫米时等比缩小到 270）')
        self.force_small_pair.setChecked(preferences.value('developer/force_small_pair_width', False, bool))
        self.force_small_pair.setToolTip('仅开发者模式生效；不放大小图，XL 及以上不处理，刀码仍按区域统一刀位。')
        self.tail_rotation = QCheckBox('单件批次末尾 3XL 及以上：省膜时整尺码块旋转')
        self.tail_rotation.setChecked(preferences.value('cutter/tail_rotation', True, bool))
        self.safety = self._box(3, 0.1, 30)
        self.marker_offset = self._box(0, 0, 100)
        self.left_marker_lift = self._box(preferences.value('cutter/left_marker_lift_mm',1.5,float),0,30)
        self.left_marker_lift.valueChanged.connect(lambda v: preferences.setValue('cutter/left_marker_lift_mm',v))
        self.transitions = TransitionSettings(preferences, self)
        self.compare_films = QCheckBox('比较45/60厘米：常规与旋转（不自动切换，结果存入历史）')
        if not preferences.value('cutter/film_comparison_default_v2', False, bool):
            preferences.setValue('cutter/compare_films', True)
            preferences.setValue('cutter/film_comparison_default_v2', True)
        self.compare_films.setChecked(preferences.value('cutter/compare_films', True, bool))
        self.compare_films.toggled.connect(lambda v: preferences.setValue('cutter/compare_films', v))
        note = QLabel(
            "先选择膜规格，再选择排版模式。固定双列的刀位整批不变；"
            "右侧色块左边缘 = 刀位 + 安全距离 + 色块偏移。"
            "常规区保持固定刀位；旋转区每行一张，完整订单迁移。图片必须有可靠 DPI。"
        )
        note.setWordWrap(True)
        form = QFormLayout(self)
        for text, control in (
            ('处理模式', self.quick_mode),
            ("膜规格", self.film), ("生产排版模式", self.mode),
            ('', self.custom_film),
            ('RIIN 已设置的预留', self.printable),
            ("刀位选择", self.auto_knife),
            ("旋转区域", self.rotation_zone),
            ('双排集中', self.two_zone),
            ('强制双排实验', self.force_small_pair),
            ('快速末尾旋转', self.tail_rotation),
            ('区域与批次提示', self.transitions),
            ('膜规格比较', self.compare_films),
            ("刀位距排版左边（毫米）", self.knife),
            ("刀位两侧安全距离（毫米）", self.safety),
            ("右侧色块基准偏移（毫米）", self.marker_offset), ("", note),
            ('左图刀码高于图片（毫米，占用现有垂直间距）', self.left_marker_lift),
        ):
            form.addRow(text, control)
        self.form = form
        self.force_small_pair_label = form.labelForField(self.force_small_pair)
        self.set_developer_mode(False)
        previous_width = int(width.value())
        default_film = previous_width if previous_width in {450, 600} else 600
        film = preferences.value("cutter/film_mm", default_film, float)
        if preferences.value('cutter/custom_film_selected',film not in {450,600},bool):
            self.custom_film.value.setValue(film/10)
            film='custom'
        self.film.setCurrentIndex(max(0, self.film.findData(film)))
        self._initializing = True
        self._film_changed()
        mode = preferences.value("cutter/mode", self.mode.currentData(), str)
        self.mode.setCurrentIndex(max(0, self.mode.findData(mode)))
        for control, key, default in (
            (self.knife, "knife_mm", max(1, self.printable.usable_width() / 2)),
            (self.safety, "safety_mm", 3),
            (self.marker_offset, "marker_offset_mm", 0),
        ):
            control.setValue(preferences.value("cutter/" + key, default, float))
        self._initializing = False
        self.film.currentIndexChanged.connect(self._film_changed)
        self.custom_film.value.valueChanged.connect(self._custom_width_changed)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.auto_knife.toggled.connect(self._mode_changed)
        self.quick_mode.toggled.connect(self._mode_changed)
        self.rotation_zone.toggled.connect(self._rotation_requested)
        self.two_zone.toggled.connect(self._two_zone_requested)
        self.force_small_pair.toggled.connect(self._force_small_pair_requested)
        self._mode_changed()

    def _film_changed(self, *_args):
        custom=self.film.currentData()=='custom'
        self.custom_film.setVisible(custom)
        film = self.custom_film.millimetres() if custom else self.film.currentData()
        self.width_control.setValue(film)
        self.mode.blockSignals(True)
        self.mode.clear()
        modes = (
            [("单列切膜（默认）", "single"), ("固定双列切膜（小图）", "dual")]
            if film == 450 else
            [("固定双列切膜（默认）", "dual"), ("单列切膜", "single")]
        )
        for text, value in modes + [("正常排版（无刀码）", "free")]:
            self.mode.addItem(text, value)
        self.mode.blockSignals(False)
        self.printable.refresh()
        self.knife.setValue(max(1, self.printable.usable_width() / 2))
        self._mode_changed()

    def _custom_width_changed(self, *_args):
        if self.film.currentData()=='custom':
            self.width_control.setValue(self.custom_film.millimetres())
            self.printable.refresh()

    def _mode_changed(self, *_args):
        if getattr(self, "_initializing", False):
            return
        mode = self.mode.currentData()
        for control in (self.knife, self.safety, self.marker_offset):
            control.setEnabled(mode == "dual")
        self.auto_knife.setEnabled(mode == "dual")
        self.rotation_zone.setEnabled(mode == "dual")
        self.two_zone.setEnabled(mode == 'dual')
        self.force_small_pair.setEnabled(mode == 'dual')
        self.tail_rotation.setEnabled(mode == 'dual')
        if self.quick_mode.isChecked():
            self.rotation_zone.setChecked(False)
        self.knife.setEnabled(mode == "dual" and not self.auto_knife.isChecked())
        self.rotation.setEnabled(mode == "free" and not self.quick_mode.isChecked())
        self.direction.setEnabled(mode == "free" and not self.quick_mode.isChecked())
        if mode != "free" or self.quick_mode.isChecked():
            self.rotation.setChecked(False)
        if self.block is not None:
            for control in (self.block.enabled, self.block.position, self.block.offset_y):
                control.setEnabled(False)
            if mode=='free':
                self.block.enabled.setChecked(False)
            if mode != "free":
                self.block.enabled.setChecked(True)
                self.block.position.setCurrentIndex(self.block.position.findData("left_top"))
                self.block.offset_y.setValue(0)
        self.transitions.setEnabled(mode!='free')

    def save(self):
        self.printable.save()
        for key, value in {
            'quick_mode': self.quick_mode.isChecked(),
            "film_mm": self.width_control.value(), "mode": self.mode.currentData(),
            'custom_film_selected': self.film.currentData()=='custom',
            "auto_knife": self.auto_knife.isChecked(),
            "rotation_zone": self.rotation_zone.isChecked(),
            'tail_rotation': self.tail_rotation.isChecked(),
            "knife_mm": self.knife.value(), "safety_mm": self.safety.value(),
            "marker_offset_mm": self.marker_offset.value(),
            'left_marker_lift_mm': self.left_marker_lift.value(),
        }.items():
            self.preferences.setValue("cutter/" + key, value)
        self.preferences.setValue('layout/majority_two_zone', self.two_zone.isChecked())
        self.preferences.setValue('developer/force_small_pair_width', self.force_small_pair.isChecked())

    def _rotation_requested(self, enabled):
        if enabled and self.mode.currentData() == 'dual':
            self.quick_mode.setChecked(False)
            self.tail_rotation.setChecked(False)

    def _two_zone_requested(self, enabled):
        self.preferences.setValue('layout/majority_two_zone', enabled)
        if enabled and self.mode.currentData() == 'dual':
            self.quick_mode.setChecked(False)
            self.rotation_zone.setChecked(True)
            self.tail_rotation.setChecked(False)

    def _force_small_pair_requested(self, enabled):
        self.preferences.setValue('developer/force_small_pair_width', enabled)
        if enabled and self.mode.currentData() == 'dual':
            self.two_zone.setChecked(True)

    def set_developer_mode(self, enabled):
        self.force_small_pair.setVisible(enabled)
        self.force_small_pair_label.setVisible(enabled)

    @staticmethod
    def _box(value, minimum, maximum):
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setDecimals(1)
        box.setValue(value)
        return box
