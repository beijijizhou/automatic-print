"""Canonical actual cutter positions for a planned or rendered placement."""


def knife_signature(placement):
    get = placement.get if isinstance(placement, dict) else lambda key: getattr(placement, key)
    knives = get('cut_knife_xs_px') or ()
    if not knives and get('cut_knife_x_px') is not None:
        knives = (get('cut_knife_x_px'),)
    return tuple(knives)


def actual_knife_signatures(result):
    return {knife_signature(placement) for placement in result.get('placements') or ()}
