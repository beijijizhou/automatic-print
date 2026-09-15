"""Canonical extraction of actual knife positions from a completed plan."""


def knife_pixels(planned):
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
