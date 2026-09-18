"""Stop-distance protection between left sensor marks when knife positions change."""
from collections import defaultdict
from dataclasses import replace

from automatic_print.layout_engine.domain.models import mm_to_px


def knife_pixels(planned):
    """Return every fixed vertical knife from the completed plan."""
    for _path, placement in planned:
        if placement.cut_knife_xs_px:
            return tuple(placement.cut_knife_xs_px)
        if placement.cut_knife_x_px is not None:
            return (placement.cut_knife_x_px,)
    return ()


def knife_millimetres(planned, dpi):
    return tuple(round(value * 25.4 / dpi, 3) for value in knife_pixels(planned))


def result_fields(planned, settings):
    knives = knife_millimetres(planned, settings.dpi)
    first = knives[0] if knives else None
    return {'cutter_knife_mm': first, 'cutter_knives_mm': list(knives),
            'right_marker_mm': (first + settings.cutter_safety_mm
                                + settings.cutter_marker_offset_mm)
            if first is not None else None}


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


def _record(previous_signature, signature, previous_zone, zone, required, actual,
            added=0, removed=0):
    return {
        'from_zone': previous_zone or '上一区域',
        'to_zone': zone or '下一区域',
        'from_knives_px': previous_signature,
        'to_knives_px': signature,
        'required_px': required,
        'actual_px': actual,
        'added_px': added,
        'removed_px': removed,
    }


def apply_knife_change_gap(result, settings):
    """Protect knife changes and the batch end with a left-marker stop distance."""
    planned, labels, width, height, baseline = result
    required = mm_to_px(settings.cutter_knife_change_gap_mm, settings.dpi)
    if not required or settings.cutter_mode != 'dual':
        return result, []
    shifts, records = {}, []
    cumulative = 0
    shifted_any = False
    previous_signature = previous_marker = previous_zone = None
    previous_bottom = None
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    for row in _rows(planned):
        signature, marker, zone = _row_facts(row)
        if signature is None or marker is None:
            continue
        row_top = min(placement.row_y_px for _path, placement in row) + cumulative
        row_bottom = max(placement.row_y_px + placement.footprint_height_px
                         for _path, placement in row) + cumulative
        marker += cumulative
        if previous_signature is not None and signature != previous_signature:
            actual = marker - previous_marker
            adjustment = required - actual
            if adjustment < 0 and previous_bottom is not None:
                adjustment = max(adjustment, previous_bottom + spacing - row_top)
            cumulative += adjustment
            marker += adjustment
            row_top += adjustment
            row_bottom += adjustment
            shifted_any = shifted_any or bool(adjustment)
            records.append(_record(
                previous_signature, signature, previous_zone, zone,
                required, marker - previous_marker,
                max(0, adjustment), max(0, -adjustment),
            ))
        for path, placement in row:
            shifts[(str(path), placement.sequence_number)] = cumulative
        previous_signature, previous_marker, previous_zone = signature, marker, zone
        previous_bottom = row_bottom
    if previous_marker is not None:
        actual = height + cumulative - previous_marker
        added = max(0, required - actual)
        cumulative += added
        shifted_any = shifted_any or bool(added)
        records.append(_record(
            previous_signature, (), previous_zone, '批次结束',
            required, actual + added, added,
        ))
    if not shifted_any:
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


def inspect_knife_change_gaps(planned, settings, canvas_height=None):
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
            records.append(_record(
                previous_signature, signature, previous_zone, zone,
                required, marker - previous_marker,
            ))
        previous_signature, previous_marker, previous_zone = signature, marker, zone
    if previous_marker is not None and canvas_height is not None:
        records.append(_record(
            previous_signature, (), previous_zone, '批次结束',
            required, canvas_height - previous_marker,
        ))
    return records
