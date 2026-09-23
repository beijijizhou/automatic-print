"""Shared progress calculations for local layout generation."""


READING_STAGES = {'分析批次', '读取图片尺寸', '测量标签与刀码'}
LAYOUT_STAGES = {
    '识别膜标签', '膜规格比较', '整理双面图片', '切膜安全检查',
    '计算排版', '计算批次刀位', '批次刀位已确定', '比较旋转区域',
}


def progress_percent(stage: str, current: int, total: int) -> int:
    ratio = current / total if total else 0
    if stage == '扫描文件夹':
        return 0
    if stage in READING_STAGES:
        return round(ratio * 20) if stage == '分析批次' else 20 + round(ratio * 25)
    if stage in LAYOUT_STAGES:
        return 45
    if stage == '合成图片':
        return 45 + round(ratio * 45)
    return 95


def remaining_seconds(stage: str, current: int, total: int, elapsed: float):
    if not current or stage not in {'读取图片尺寸', '识别膜标签', '合成图片'}:
        return None
    return elapsed / current * max(0, total - current)


def progress_count(stage: str, current: int, total: int) -> str:
    if stage == '扫描文件夹':
        return '正在扫描图片文件名'
    if stage == '保存图片':
        return '正在持续写入磁盘'
    return f'{current}/{total}'
