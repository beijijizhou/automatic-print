"""Shared progress calculations and machine-status projection."""

from datetime import datetime, timezone


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


def begin_machine_task(window, batch_id, batch_name, *, batch_info=None):
    window.machine_status_batch_id = str(batch_id)
    window.machine_status_batch_name = str(batch_name)
    window.machine_status_started_at = datetime.now(timezone.utc).isoformat()
    report_machine_progress(window, '正在开始', 0, batch_info=batch_info or {})


def report_machine_progress(
    window, phase, percent=None, *, remaining=None, batch_name=None,
    batch_info=None, state='running', estimate_scope=None, error_message=None,
):
    if not getattr(window, 'developer_mode_enabled', False):
        return
    window.machine_status_reporter.publish(
        department='DTF', state=state, phase=phase,
        progress_percent=percent,
        batch_id=window.machine_status_batch_id or None,
        batch_name=batch_name or window.machine_status_batch_name or None,
        batch_info=batch_info or {},
        remaining_seconds=round(remaining) if remaining is not None else None,
        estimate_scope=estimate_scope or ('phase' if remaining is not None else None),
        started_at=window.machine_status_started_at,
        error_message=error_message,
    )
