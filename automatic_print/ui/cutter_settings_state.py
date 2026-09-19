"""Persistence for cutter controls, kept separate from widget construction."""

DEFAULT_KNIFE_CHANGE_GAP_MM = 600


def pair_width_limit(preferences):
    from .spinbox_style import double_spinbox
    box = double_spinbox(preferences.value('layout/force_small_pair_source_limit_mm', 310, float),
                         1, 1000, decimals=0)
    box.setSuffix(' 毫米')
    box.setToolTip('S–XL 原图宽度不超过此值时，允许按膜宽和刀码安全占位等比缩小；共刀多批次也使用此值。')
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
