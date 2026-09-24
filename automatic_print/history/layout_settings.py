"""Persist the complete local layout configuration for headless automation."""

from dataclasses import asdict, fields, replace
import json

from automatic_print.layout_engine import LayoutSettings


SNAPSHOT_KEY = "layout/settings_snapshot_v1"
_TUPLE_FIELDS = {
    "dimension_overrides",
    "header_gap_overrides",
    "width_adjustments",
    "force_small_pair_sizes",
    "manual_rotations",
    "sequence_numbers",
}


def save_layout_settings(preferences, settings: LayoutSettings) -> None:
    """Save only reusable machine settings; omit per-run knife locks."""
    stable = replace(
        settings,
        strict_fixed_knife=False,
        order_side_shared_knife=False,
        sequence_numbers=(),
        label_sequence_total=0,
        label_batch_name="",
    )
    preferences.setValue(
        SNAPSHOT_KEY,
        json.dumps(asdict(stable), ensure_ascii=False, separators=(",", ":")),
    )


def load_layout_settings(
    preferences,
    fallback: LayoutSettings | None = None,
) -> LayoutSettings:
    """Load this machine's settings, with legacy cutter preferences as fallback."""
    fallback = fallback or LayoutSettings(png_engine="libvips")
    raw = preferences.value(SNAPSHOT_KEY, "", str)
    if raw:
        try:
            values = json.loads(raw)
            allowed = {field.name for field in fields(LayoutSettings)}
            clean = {key: value for key, value in values.items() if key in allowed}
            for key in _TUPLE_FIELDS & clean.keys():
                clean[key] = tuple(tuple(item) if isinstance(item, list) else item
                                   for item in clean[key])
            return LayoutSettings(**clean)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return _legacy_layout_settings(preferences, fallback)


def _legacy_layout_settings(preferences, fallback):
    film = preferences.value(
        "cutter/film_mm",
        preferences.value("layout/media_width_mm", 600, float),
        float,
    )
    left = preferences.value("riin/left_mm", 15, float)
    right = preferences.value("riin/right_mm", 15, float)
    width = max(1, film - left - right)
    sizes = tuple(
        item.strip().upper()
        for item in preferences.value(
            "layout/force_small_pair_sizes", "S,M,L,XL", str,
        ).split(",")
        if item.strip()
    )
    mode = preferences.value("cutter/mode", fallback.cutter_mode, str)
    quick = preferences.value("cutter/quick_mode", True, bool)
    return replace(
        fallback,
        media_width_mm=width,
        fixed_output_width_mm=width,
        riin_left_mm=left,
        riin_right_mm=right,
        cutter_mode=mode if mode in {"free", "single", "dual"} else fallback.cutter_mode,
        cutter_auto_knife=preferences.value(
            "cutter/auto_knife", fallback.cutter_auto_knife, bool,
        ),
        cutter_knife_mm=preferences.value(
            "cutter/knife_mm", width / 2, float,
        ),
        cutter_safety_mm=preferences.value(
            "cutter/safety_mm", fallback.cutter_safety_mm, float,
        ),
        cutter_marker_offset_mm=preferences.value(
            "cutter/marker_offset_mm", fallback.cutter_marker_offset_mm, float,
        ),
        cutter_left_marker_lift_mm=preferences.value(
            "cutter/left_marker_lift_mm", fallback.cutter_left_marker_lift_mm, float,
        ),
        cutter_rotation_zone=(not quick and preferences.value(
            "cutter/rotation_zone", fallback.cutter_rotation_zone, bool,
        )),
        cutter_tail_rotation=preferences.value(
            "cutter/tail_rotation", fallback.cutter_tail_rotation, bool,
        ),
        cutter_majority_two_zone=preferences.value(
            "layout/majority_two_zone", fallback.cutter_majority_two_zone, bool,
        ),
        force_small_pair_width=preferences.value(
            "layout/force_small_pair_width", fallback.force_small_pair_width, bool,
        ),
        force_small_pair_source_limit_mm=preferences.value(
            "layout/force_small_pair_source_limit_mm",
            fallback.force_small_pair_source_limit_mm,
            float,
        ),
        force_small_pair_sizes=sizes,
        machine_number=preferences.value(
            "layout/machine_number", fallback.machine_number, str,
        ).upper(),
        color_block_enabled=(mode != "free" and preferences.value(
            "color_block/enabled", True, bool,
        )),
    )
