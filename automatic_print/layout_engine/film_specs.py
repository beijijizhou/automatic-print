"""Comparison inventory; reference widths never change production settings."""
FILM_WIDTHS = (600, 450, 400, 500, 550, 650, 700, 750, 800)
AVAILABLE_WIDTHS = frozenset((600, 450))
COMPARISON_COUNT = len(FILM_WIDTHS) * 2


def comparison_widths(include_references=False):
    return FILM_WIDTHS if include_references else (600, 450)


def availability_text(width):
    return '现有规格' if width in AVAILABLE_WIDTHS else '暂无规格，仅供参考'
