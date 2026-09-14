"""Use the same single-piece policy, restricted to the existing large-size tail."""
from dataclasses import replace

from .cutter_planner import plan_cutter_layout
from .single_rotation import eligible_tail, plan_single_rotation
from .source_metadata import source_size, size_key
from .measurement_session import resolved_name


def plan_tail_rotation(paths, settings, progress):
    from .rotation_zones import rotation_items
    effective = [settings]

    def report(stage, current, total, filename):
        if stage == '批次刀位已确定':
            effective[0] = replace(settings, cutter_knife_mm=current*25.4/total)
        if progress:
            progress(stage, current, total, filename)

    baseline = plan_cutter_layout(paths, settings, report)
    tail = eligible_tail(paths, baseline)
    if tail is None:
        return baseline
    targets = [p for p in tail if 80 <= size_key(source_size(p))[0] < 1000]
    if not targets:
        return baseline
    sequence = settings.sequence_numbers or tuple((resolved_name(p), i) for i, p in enumerate(paths, 1))
    options, labels = rotation_items(targets, replace(settings, sequence_numbers=sequence), progress)

    def selected_progress(stage, current, total, filename):
        report('比较末尾旋转' if stage == '单件旋转筛选' else stage, current, total, filename)

    return plan_single_rotation(baseline, targets, options, labels, effective[0], selected_progress)
