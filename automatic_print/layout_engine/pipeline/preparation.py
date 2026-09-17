"""Preparation callbacks shared by the layout pipeline."""
from dataclasses import replace


def gap_premeasure(paths, settings):
    from automatic_print.layout_engine.labeling.gap.virtual import enabled
    if settings.membrane_gap_mm <= 0 or not enabled(settings):
        return None
    from automatic_print.layout_engine.intake.preparation.item_factory import read_items
    from automatic_print.layout_engine.measurement.measurement_session import resolved_name

    def premeasure(index, path, local_settings):
        measured = replace(
            local_settings,
            sequence_numbers=((resolved_name(path), index + 1),),
            label_sequence_total=(local_settings.label_sequence_total or len(paths)),
        )
        read_items([path], measured, None)

    return premeasure
