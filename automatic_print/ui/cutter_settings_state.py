"""Persistence for cutter controls, kept separate from widget construction."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QToolButton

DEFAULT_KNIFE_CHANGE_GAP_MM = 600
PAIR_SIZE_OPTIONS = ('S', 'M', 'L', 'XL', '2XL', '3XL', '4XL', '5XL')
DEFAULT_PAIR_SIZES = PAIR_SIZE_OPTIONS[:4]


class PairSizeSelector(QToolButton):
    sizesChanged = Signal(object)

    def __init__(self, sizes, parent=None):
        super().__init__(parent)
        self.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self)
        self.setMenu(menu)
        self._actions = {}
        for size in PAIR_SIZE_OPTIONS:
            action = menu.addAction(size)
            action.setCheckable(True)
            action.toggled.connect(self._changed)
            self._actions[size] = action
        self.setToolTip('勾选允许为并排等比缩小的尺码；不勾选的尺码按原尺寸规划。')
        self.set_selected_sizes(sizes)
        self._changed()

    def selected_sizes(self):
        return tuple(size for size in PAIR_SIZE_OPTIONS if self._actions[size].isChecked())

    def set_selected_sizes(self, sizes):
        chosen = set(sizes) & set(PAIR_SIZE_OPTIONS)
        if self.selected_sizes() == tuple(size for size in PAIR_SIZE_OPTIONS if size in chosen):
            return
        for size, action in self._actions.items():
            previous = action.blockSignals(True)
            action.setChecked(size in chosen)
            action.blockSignals(previous)
        self._changed()

    def _changed(self, *_args):
        sizes = self.selected_sizes()
        self.setText('尺码：' + ('、'.join(sizes) if sizes else '未选择'))
        self.sizesChanged.emit(sizes)


def pair_size_selector(preferences):
    key = 'layout/force_small_pair_sizes'
    saved = preferences.value(key, '', str)
    sizes = DEFAULT_PAIR_SIZES if not preferences.contains(key) else tuple(
        size.strip().upper() for size in str(saved).split(',') if size.strip())
    control = PairSizeSelector(sizes)
    control.sizesChanged.connect(
        lambda values: preferences.setValue(key, ','.join(values)))
    return control


def pair_width_limit(preferences):
    from .spinbox_style import double_spinbox
    box = double_spinbox(preferences.value('layout/force_small_pair_source_limit_mm', 310, float),
                         1, 1000, decimals=0)
    box.setSuffix(' 毫米')
    box.setToolTip('所选尺码的原图宽度不超过此值时，允许按膜宽和刀码安全占位等比缩小；共刀多批次也使用此值。')
    box.valueChanged.connect(lambda value: preferences.setValue('layout/force_small_pair_source_limit_mm', value))
    return box


def load_knife_change_gap(preferences) -> float:
    value = preferences.value(
        'cutter/knife_change_gap_mm', DEFAULT_KNIFE_CHANGE_GAP_MM, float)
    if not preferences.value('cutter/knife_change_gap_default_v2', False, bool):
        if value == 570:
            value = DEFAULT_KNIFE_CHANGE_GAP_MM
            preferences.setValue('cutter/knife_change_gap_mm', value)
        preferences.setValue('cutter/knife_change_gap_default_v2', True)
    return value


def save_cutter_settings(panel):
    panel.printable.save()
    values = {
        'quick_mode': panel.quick_mode.isChecked(),
        'film_mm': panel.width_control.value(),
        'mode': panel.mode.currentData(),
        'custom_film_selected': panel.film.currentData() == 'custom',
        'auto_knife': panel.auto_knife.isChecked(),
        'rotation_zone': panel.rotation_zone.isChecked(),
        'tail_rotation': panel.tail_rotation.isChecked(),
        'knife_mm': panel.knife.value(),
        'safety_mm': panel.safety.value(),
        'marker_offset_mm': panel.marker_offset.value(),
        'left_marker_lift_mm': panel.left_marker_lift.value(),
        'knife_change_gap_mm': panel.knife_change_gap.value(),
    }
    for key, value in values.items():
        panel.preferences.setValue('cutter/' + key, value)
    panel.preferences.setValue(
        'layout/majority_two_zone', panel.two_zone.isChecked())
    panel.preferences.setValue(
        'layout/force_small_pair_width', panel.force_small_pair.isChecked())
    panel.preferences.setValue(
        'layout/force_small_pair_source_limit_mm', panel.force_small_pair_limit.value())
    panel.preferences.setValue(
        'layout/force_small_pair_sizes', ','.join(panel.force_small_pair_sizes.selected_sizes()))
