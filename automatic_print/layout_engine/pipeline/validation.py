"""Shared production-plan safety gate with preview-only warning recovery."""
from automatic_print.layout_engine.cutting.validation.cut_validation import (
    validate_cut_corridor,
)
from automatic_print.layout_engine.cutting.validation.order_validation import (
    validate_order_placements,
)
from automatic_print.layout_engine.labeling.markers.marker_space import (
    validate_embedded_marks,
)


def validate_plan(paths, planned, settings, width, height, preview_only):
    warning, order_check, cut_check = '', {}, {}
    try:
        if settings.order_side_shared_knife:
            from automatic_print.layout_engine.cutting.validation.order_side_validation import validate_order_side_placements
            from automatic_print.layout_engine.domain.models import mm_to_px
            order_check = validate_order_side_placements(
                paths, planned, mm_to_px(settings.cutter_knife_mm, settings.dpi))
        else:
            order_check = validate_order_placements(paths, planned)
        if settings.cutter_mode != 'free':
            cut_check = validate_cut_corridor(
                planned, settings, width, canvas_height=height,
            )
            validate_embedded_marks(planned, settings)
    except ValueError as error:
        if not preview_only:
            raise
        warning = f'仅供检查，禁止输出：{error}'
    return warning, order_check, cut_check
