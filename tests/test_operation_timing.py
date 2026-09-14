import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pathlib import Path
from PIL import Image
from PySide6.QtWidgets import QApplication

from automatic_print.layout import LayoutSettings
from automatic_print.layout_engine.operation_timing import OperationTiming
from automatic_print.ui.workers import GenerateWorker
from automatic_print.ui.worker_bridge import MainWindowWorkerBridge
from automatic_print.ui.operation_timing import OperationTimingPanel

APP = QApplication.instance() or QApplication([])
OWNERS = []


def test_exclusive_timings_accumulate_repeated_phases_and_freeze():
    clock = [10.0]
    timer = OperationTiming(lambda: clock[0])
    timer.phase('扫描文件名')
    clock[0] += 2
    timer.phase('读取尺寸与标签')
    clock[0] += 3
    timer.phase('扫描文件名')
    clock[0] += 1
    result = timer.finish('已停止')
    assert [s['seconds'] for s in result['steps']] == [3, 3]
    assert result['total_seconds'] == 6
    assert not any(s['running'] for s in result['steps'])
    clock[0] += 100
    assert timer.snapshot() == result


def test_worker_reports_scan_through_output_and_persists_timings(tmp_path):
    import json
    source = tmp_path/'batch123'
    source.mkdir()
    for i in range(3):
        Image.new('RGBA', (40, 60), 'blue').save(source/f'B{i}-1-T-Black-M-NO1-1.png', dpi=(25.4,25.4))
    worker = GenerateWorker(None, source, tmp_path/'out', 'JOB', LayoutSettings(
        dpi=25.4, cutter_mode='dual', cutter_auto_knife=True, number_images=False))
    updates, finished, failures = [], [], []
    worker.timings_ready.connect(updates.append)
    worker.finished.connect(lambda output, result: finished.append(result))
    worker.failed.connect(failures.append)
    worker.run()
    assert not failures
    result = finished[0]['operation_timings']
    names = [row['name'] for row in result['steps']]
    assert names[0] == '扫描文件名'
    assert {'读取尺寸与标签', '刀位与排版计算', '图片准备与合成',
            '合成像素安全检查', '膜标签与辅助线处理', '保存输出图片'} <= set(names)
    assert abs(sum(s['seconds'] for s in result['steps'])-result['total_seconds']) < .01
    assert result['status'] == '已完成'
    manifest = json.loads((worker.output/'manifest.json').read_text())
    assert manifest['print_image']['operation_timings'] == result
    assert updates[-1] == result
    report = (worker.output/'排版报告.txt').read_text()
    assert '扫描文件名' in report and '最耗时步骤' in report
    assert '耗时与并行处理' in report
    assert not (worker.output/'耗时报告.txt').exists()
    assert not (tmp_path/'out'/'切割说明.txt').exists()


def test_failure_and_cancel_stop_timer(tmp_path):
    for cancelled in (False, True):
        worker = GenerateWorker(None, tmp_path, tmp_path/'out', 'JOB', LayoutSettings())
        snapshots = []
        worker.timings_ready.connect(snapshots.append)
        if cancelled:
            worker.request_cancel()
        worker.run()
        assert snapshots[-1]['status'] == ('已停止' if cancelled else '失败')
        assert not any(row['running'] for row in snapshots[-1]['steps'])


def test_visible_copyable_report_and_new_task_reset():
    bridge = MainWindowWorkerBridge()
    panel = OperationTimingPanel(bridge)
    OWNERS.extend((bridge, panel))
    timer = OperationTiming()
    timer.phase('读取尺寸与标签')
    bridge.layout_timings.emit(timer.finish())
    assert panel.table.rowCount() == 1
    assert '读取尺寸与标签' in panel.summary.text()
    assert not panel.timer.isActive()
    panel.copy_report()
    assert '读取尺寸与标签' in APP.clipboard().text()
    panel.reset()
    assert panel.table.rowCount() == 0
    assert panel.data is None
    panel.close()
