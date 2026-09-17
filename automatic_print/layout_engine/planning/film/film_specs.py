"""Production comparison inventory; only supported film widths are listed."""
FILM_WIDTHS = (600, 450)
AVAILABLE_WIDTHS = frozenset((600, 450))
COMPARISON_COUNT = len(FILM_WIDTHS) * 2


def comparison_widths(include_references=False):
    return FILM_WIDTHS


def availability_text(width):
    return '现有规格' if width in AVAILABLE_WIDTHS else '暂无规格，仅供参考'
