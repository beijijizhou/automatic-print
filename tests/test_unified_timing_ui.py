"""All generation entry points use the same live timing table."""
from pathlib import Path
from time import perf_counter
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QPushButton

from automatic_print.ui.bulk_workbench import BulkWorkbench
from automatic_print.ui.cold_batch_benchmark import ColdBatchBenchmarkDialog
from automatic_print.ui.operation_timing import OperationTimingPanel
from automatic_print.layout_engine.orders.batch_analysis import batch_inventory
from test_developer_mode import APP, window


def snapshot(status, seconds=1.0):
    return dict(status=status, total_seconds=seconds, captured_at=perf_counter(),
                active_phase='读取图片尺寸' if status == '运行中' else None,
                steps=[dict(name='读取图片尺寸', seconds=seconds,
                            running=status == '运行中')])


def test_single_bulk_and_random_ten_share_live_table(tmp_path):
    owner = window(tmp_path/'timings.ini')
    panel = owner.automation_home.label_quick_panel.timings
    assert isinstance(panel, OperationTimingPanel)
    controller = BulkWorkbench(owner)
    owner.generation_preview.mode = 'multiple'
    controller.folders = [Path(tmp_path/'one'), Path(tmp_path/'two')]
    controller.inventory = {}
    controller.payloads, controller.records, controller.stages = {}, {}, {}
    controller.timing_data = {}
    controller.selector.reset(controller.folders)
    controller.timings(0, snapshot('已完成'))
    controller.timings(1, snapshot('运行中'))
    assert controller.selector.currentIndex() == 1
    assert panel.data['status'] == '运行中'
    assert panel.table.item(0, 2).text().endswith('进行中')

    controller.selector.groups['未完成'].setCurrentItem(controller.selector.items[0])
    APP.processEvents()
    assert not controller.follow_active_batch
    controller.timings(1, snapshot('运行中', 2.0))
    assert controller.selector.currentIndex() == 0
    assert panel.data['status'] == '已完成'

    dialog = ColdBatchBenchmarkDialog(owner)
    assert isinstance(dialog.timing_panel, OperationTimingPanel)
    dialog.layout_timings.emit(snapshot('运行中'))
    assert dialog.timing_panel.table.item(0, 2).text().endswith('进行中')
    dialog.close()
    owner.close()


def test_single_and_bulk_share_three_column_batch_records(tmp_path):
    owner = window(tmp_path/'batch-board.ini')
    source = tmp_path/'single-batch'
    source.mkdir()
    owner.folder.setText(str(source))
    board = owner.batch_status_board
    owner.generation_preview.start()
    assert board.isVisibleTo(owner)
    assert board.groups['未完成'].topLevelItemCount() == 1
    assert board.items[0].text(0) == source.name
    owner.generation_preview.sources([source/'one.png', source/'two.png'])
    owner.worker_bridge.layout_analysis.emit(batch_inventory([
        source/'B1-1-T-Black-S-NO1-1.png',
        source/'B2-1-T-Black-M-NO1-1.png',
    ]))
    assert board.items[0].text(2) == 'S 1件 · M 1件'
    owner.generation_preview.progress('读取图片尺寸', 1, 2, 'one.png')
    APP.processEvents()
    panel = owner.automation_home.label_quick_panel
    assert board.parentWidget() is panel
    assert board.geometry().bottom() < panel.summary.geometry().top()
    assert board.groups['进行中'].topLevelItemCount() == 1
    assert board.items[0].text(1) == '2'
    assert 'one.png' in board.items[0].toolTip(0)
    board.open_record.click()
    assert owner.generation_preview.record_dialog.isVisible()
    assert str(source) in owner.generation_preview.record_dialog.details.toPlainText()
    owner.generation_preview.record_dialog.close()
    APP.processEvents()
    assert board.grab().save(str(tmp_path/'unified-single-board.png'))
    owner.worker_bridge.layout_finished.emit(str(tmp_path), {'preview_only': True})
    assert board.groups['已完成'].topLevelItemCount() == 1

    controller = BulkWorkbench(owner)
    assert controller.selector is board
    owner.generation_preview.start('multiple')
    assert board.groups['已完成'].topLevelItemCount() == 0
    controller.selector.reset([source, tmp_path/'second-batch'])
    assert board.groups['未完成'].topLevelItemCount() == 2
    owner.close()


def test_single_failed_batch_stays_visible_with_reason(tmp_path):
    owner = window(tmp_path/'failed-board.ini')
    source = tmp_path/'failed-batch'
    owner.folder.setText(str(source))
    owner.generation_preview.start()
    owner.generation_preview.progress('测量标签与刀码', 1, 4, 'problem.png')
    owner.generation_preview.failed('problem.png 标签位置不足')
    board = owner.batch_status_board
    assert board.groups['未完成'].topLevelItemCount() == 1
    assert 'problem.png 标签位置不足' in board.items[0].toolTip(0)
    owner.close()


def test_summary_shows_copyable_selected_batch_record(tmp_path):
    owner = window(tmp_path/'visible-record.ini')
    record = owner.batch_record_view
    summary = owner.automation_home.label_quick_panel.summary
    assert summary.isAncestorOf(record)
    assert record.isVisible() and record.height() <= 160
    timings = owner.automation_home.label_quick_panel.timings
    assert record.geometry().top() > timings.mapTo(summary, QPoint(0, timings.height())).y()
    assert '尚无批次记录' in record.toPlainText()

    owner.generation_preview.start('single')
    owner.run_log.appendPlainText('开始：读取图片尺寸')
    assert '开始：读取图片尺寸' in record.toPlainText()

    first, second = tmp_path/'first', tmp_path/'second'
    controller = BulkWorkbench(owner)
    owner.bulk_controller = controller
    controller.folders = [first, second]
    controller.inventory = {}
    controller.payloads, controller.records, controller.stages = {}, {}, {}
    controller.timing_data = {}
    owner.generation_preview.start('multiple')
    controller.selector.reset(controller.folders)
    owner.run_log.clear()
    owner.run_log.appendPlainText('first：读取图片尺寸')
    owner.run_log.appendPlainText('second：保存输出图片')
    assert 'first：读取图片尺寸' in record.toPlainText()
    assert 'second：保存输出图片' not in record.toPlainText()
    controller.selector.setCurrentIndex(1)
    assert 'second：保存输出图片' in record.toPlainText()
    assert 'first：读取图片尺寸' not in record.toPlainText()
    copy_button = next(button for button in summary.findChildren(QPushButton)
        if button.text() == '复制记录')
    copy_button.click()
    assert QApplication.clipboard().text() == record.toPlainText()
    owner.close()
