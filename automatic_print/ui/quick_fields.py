"""Compact label fields plus identities owned by the pinned parameter area."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel


def _selected_source_text(path, prefix='已选择排版目录'):
    return f'{prefix}：{path.name}  ·  {path}' if path else '尚未选择图片文件夹'


def show_selected_source(panel, value, mode='single', window=None):
    """Input root is distinct from the currently rendered child batch."""
    path = Path(str(value).strip()) if str(value).strip() else None
    prefix = '已选择排版目录' if mode in {'layout', 'multiple'} else '已选择'
    panel.selected_source_root = path
    panel.selected_source.setText(_selected_source_text(path, prefix))
    panel.selected_source.setToolTip(str(path) if path else '')
    panel.selected_source.setStyleSheet('QLabel { background: #dbeafe; color: #1e40af; '
        'border: 1px solid #60a5fa; border-radius: 5px; padding: 7px; font-weight: bold; }'
        if path else 'QLabel { color: #64748b; padding: 5px; }')
    if window is not None:
        window.preferences.setValue('layout/input_root', str(path) if path else '')
        window.preferences.setValue('layout/input_mode', mode)
        window.preferences.sync()


def show_selected_batch_summary(panel, folder, report=None):
    """Show the active child batch and reuse its completed in-memory analysis."""
    path = Path(str(folder).strip()) if str(folder).strip() else None
    panel.selected_batch_path = path
    if not path:
        panel.selected_source.setText('尚未选择图片文件夹')
        panel.selected_source.setToolTip('')
        return
    if not report:
        panel.selected_source.setText(_selected_source_text(path, '当前批次'))
        panel.selected_source.setToolTip(str(path))
        return
    from ..layout_engine.orders.batch_analysis import (
        compact_distribution_text, distribution_text, group_distribution,
    )
    distribution = report.get('group_distribution') or group_distribution(report)
    group_name = '尺码群' if distribution['kind'] == 'sizes' else '订单群'
    identity = (f"当前批次：{path.name} · {report.get('batch_type', '批次')}"
                f" · {report.get('order_count', 0)} 个订单组"
                f" · {report.get('piece_count', 0)} 件 / {report.get('image_count', 0)} 张图"
                f" · {report.get('double_pairs', 0)} 组双面")
    lines = [identity, f'{group_name}：{compact_distribution_text(report, limit=8)}']
    from ..automation.api.s2b.metadata.prepare import metadata_summary_text
    metadata = metadata_summary_text(report.get('s2b_metadata', ()))
    if metadata:
        lines.append(f'S2B批次信息：{metadata}')
    gap_records = report.get('header_gap', ())
    if gap_records:
        expanded = sum(record.get('added_px', 0) > 0 for record in gap_records)
        failed = sum(bool(record.get('warning')) for record in gap_records)
        satisfied = len(gap_records) - expanded - failed
        lines[-1] += (f' · 膜间距：扩充 {expanded}/{len(gap_records)} 张'
                      f'，已满足 {satisfied} 张，未扩充 {failed} 张')
    lines.append(f'来源：{path}')
    panel.selected_source.setText('\n'.join(lines))
    panel.selected_source.setToolTip(
        '\n'.join(filter(None, (distribution_text(report), metadata, f'来源：{path}')))
    )


def quick_fields(panel, date_button, window):
    row = QHBoxLayout()
    controls = (("标签与文字", panel.text, 3), ("生产平台", panel.platform, 1),
                ("平台文字高度", panel.platform_font_height, 1), ("机器号", panel.machine, 0))
    for name, control, stretch in controls:
        row.addWidget(QLabel(name))
        row.addWidget(control, stretch)
        control.setMinimumWidth(60)
        control.setToolTip(name)
    panel.platform_font_height.setMaximumWidth(125)
    panel.machine.setMaximumWidth(75)
    panel.platform.setMaximumWidth(145)
    panel.text.setMinimumWidth(120)
    panel.sequence.setParent(panel)
    panel.sequence.hide()  # Canonical sequence option remains in label settings.
    date_button.setParent(panel)
    date_button.hide()  # Date insertion remains available in the full settings.
    panel.selected_source = QLabel()
    panel.selected_source.setWordWrap(True)
    panel.selected_source.setTextInteractionFlags(Qt.TextSelectableByMouse)
    def show_source(value):
        show_selected_source(panel, value, window=window)
    window.folder.textChanged.connect(show_source)
    show_selected_source(panel, window.preferences.value('layout/input_root', window.folder.text(), str),
                         window.preferences.value('layout/input_mode', 'single', str))
    from .current_film import CurrentFilmLabel
    panel.current_film = CurrentFilmLabel(window, panel)
    # The batch input panel places both identities above all everyday options.
    # Creating them here keeps the existing data bindings owned by this module.
    return row
