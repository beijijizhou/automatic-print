"""Stop-distance protection between left sensor marks when knife positions change."""
from collections import defaultdict
from dataclasses import replace

from automatic_print.layout_engine.domain.models import mm_to_px


def knife_signature(placement):
    if placement.cut_knife_xs_px:
        return tuple(placement.cut_knife_xs_px)
    return ((placement.cut_knife_x_px,)
            if placement.cut_knife_x_px is not None else ())


def _rows(planned):
    rows = defaultdict(list)
    for path, placement in planned:
        rows[placement.row_y_px].append((path, placement))
    return [rows[y] for y in sorted(rows)]


def _row_facts(row):
    signatures = {knife_signature(placement) for _path, placement in row}
    signature = next(iter(signatures)) if len(signatures) == 1 else None
    markers = [placement.color_block_y_px for _path, placement in row
               if placement.color_block_width_px and placement.color_block_x_px == 0]
    zone = next((placement.cut_zone for _path, placement in row
                 if placement.cut_zone), '')
    return signature, min(markers) if markers else None, zone


def apply_knife_change_gap(result, settings):
    """Shift each later knife zone until consecutive left marks are far enough apart."""
    planned, labels, width, height, baseline = result
    required = mm_to_px(settings.cutter_knife_change_gap_mm, settings.dpi)
    if not required or settings.cutter_mode != 'dual':
        return result, []
    shifts, records = {}, []
    cumulative = 0
    previous_signature = previous_marker = previous_zone = None
    for row in _rows(planned):
        signature, marker, zone = _row_facts(row)
        if signature is None or marker is None:
            continue
        marker += cumulative
        if previous_signature is not None and signature != previous_signature:
            actual = marker - previous_marker
            added = max(0, required - actual)
            cumulative += added
            marker += added
            records.append({
                'from_zone': previous_zone or '上一区域',
                'to_zone': zone or '下一区域',
                'from_knives_px': previous_signature,
                'to_knives_px': signature,
                'required_px': required,
                'actual_px': marker - previous_marker,
                'added_px': added,
            })
        for path, placement in row:
            shifts[(str(path), placement.sequence_number)] = cumulative
        previous_signature, previous_marker, previous_zone = signature, marker, zone
    if not cumulative:
        return result, records
    shifted = []
    for path, placement in planned:
        offset = shifts.get((str(path), placement.sequence_number), 0)
        shifted.append((path, replace(
            placement,
            y_px=placement.y_px + offset,
            row_y_px=placement.row_y_px + offset,
            number_y_px=placement.number_y_px + offset,
            color_block_y_px=placement.color_block_y_px + offset,
            platform_y_px=placement.platform_y_px + offset,
        )))
    return (shifted, labels, width, height + cumulative, baseline), records


def inspect_knife_change_gaps(planned, settings):
    required = mm_to_px(settings.cutter_knife_change_gap_mm, settings.dpi)
    if not required or settings.cutter_mode != 'dual':
        return []
    records = []
    previous_signature = previous_marker = previous_zone = None
    for row in _rows(planned):
        signature, marker, zone = _row_facts(row)
        if signature is None or marker is None:
            continue
        if previous_signature is not None and signature != previous_signature:
            records.append({
                'from_zone': previous_zone or '上一区域',
                'to_zone': zone or '下一区域',
                'from_knives_px': previous_signature,
                'to_knives_px': signature,
                'required_px': required,
                'actual_px': marker - previous_marker,
                'added_px': 0,
            })
        previous_signature, previous_marker, previous_zone = signature, marker, zone
    return records
