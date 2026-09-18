"""Public membrane-gap facade used by generation, preview, and analysis."""
from automatic_print.layout_engine.labeling.base.header_region import search_header
from automatic_print.layout_engine.labeling.gap.cached_copy import (
    cache_root,
    prepare_one as _prepare_one,
)
from automatic_print.layout_engine.labeling.gap.batch import prepare_paths
from automatic_print.layout_engine.labeling.gap.report import (
    annotate_analysis,
    verify_records,
)
from automatic_print.layout_engine.labeling.gap.preparation import (
    gap_geometry,
    insert_gap,
)
from automatic_print.layout_engine.reporting.metrics import gap_report, gap_summary


def prepare_one(path, settings):
    return _prepare_one(path, settings, cache_root, search_header)
