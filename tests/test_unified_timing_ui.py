"""All generation entry points use the same live timing table."""
from pathlib import Path
from time import perf_counter

from automatic_print.ui.bulk_workbench import BulkWorkbench
from automatic_print.ui.cold_batch_benchmark import ColdBatchBenchmarkDialog
from automatic_print.ui.operation_timing import OperationTimingPanel
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
