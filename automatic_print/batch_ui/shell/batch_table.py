"""Render cached or live production batches into the selection table."""
from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QTableWidgetItem

from ...automation.batches.local import discover_local_batches


def display_batch_records(owner, records, saved_at='', cached=False,
                          select_ready=False) -> None:
    _update_range_choices(owner, records)
    owner.table.setRowCount(len(records))
    local_codes = {
        batch.batch_number
        for batch in discover_local_batches(
            Path(owner.output.text().strip()), owner.platform.currentData())
    }
    ready = 0
    is_s2b = owner.platform.currentData() == 'S2B'
    for row, record in enumerate(records):
        is_local = record.batch_number in local_codes
        is_ready = record.production_images_ready or is_local
        box = QCheckBox()
        box.setEnabled(is_ready)
        owner.table.setCellWidget(row, 0, box)
        values = (
            record.batch_number, str(record.item_count), str(record.piece_count),
            record.batch_type, record.generated_at,
            '本地已有' if is_local else
            ('可导出/下载' if is_s2b else '可下载') if is_ready else '生成中',
        )
        for column, value in enumerate(values, start=1):
            owner.table.setItem(row, column, QTableWidgetItem(value))
        ready += int(is_ready)
    owner.summary.setText(
        f"{owner.platform.currentText()}：显示 {len(records)} 个最新批次，"
        f"{ready} 个生产图{'可导出/下载' if is_s2b else '可下载'}。" +
        (f' 当前为本地缓存，读取时间：{saved_at}。'
         if cached and saved_at else ''))
    if select_ready:
        for row in range(owner.table.rowCount()):
            box = owner.table.cellWidget(row, 0)
            if box.isEnabled():
                box.setChecked(True)
        owner.select_button.setText('取消全选')


def _update_range_choices(owner, records) -> None:
    """Refresh both editable selectors without discarding pasted text."""
    batch_numbers = list(dict.fromkeys(
        record.batch_number for record in records if record.batch_number
    ))
    for combo in (owner.range_start, owner.range_end):
        current = combo.currentText().strip()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(batch_numbers)
        combo.setCurrentIndex(-1)
        if current:
            combo.setEditText(current)
        combo.blockSignals(False)
