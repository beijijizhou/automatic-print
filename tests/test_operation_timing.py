import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pathlib import Path
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QPushButton, QWidget

from automatic_print.layout_engine import LayoutSettings
from automatic_print.layout_engine.reporting.operation_timing import OperationTiming
from automatic_print.ui.workers import GenerateWorker
from automatic_print.ui.worker_bridge import MainWindowWorkerBridge
from automatic_print.ui.operation_timing import OperationTimingPanel
from automatic_print.ui.layout_activity import LayoutActivity

APP = QApplication.instance() or QApplication([])
OWNERS = []


def test_layout_button_shows_phase_and_total_elapsed_time():
    parent = QWidget()
    single, multiple = QPushButton('开始排版…'), QPushButton('多批次排版')
    activity = LayoutActivity(single, multiple, parent)
    OWNERS.extend((parent, activity))
    activity.start('single')
    activity.update_progress('保存图片', 17, 118)
    activity.update_phase('保存输出图片', 27.82, 38.75, .718)
    assert '进度 17/118（14.4%）' in single.text()
    assert '当前 27.82秒' in single.text()
    assert '总计 38.75秒' in single.text()
    assert '71.8%' not in single.text()
    assert '本次总耗时：38.75秒' in single.toolTip()
    assert '占当前总耗时：71.8%' in single.toolTip()
    activity.stop()


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
    source = tmp_path/'batch123'
    source.mkdir()
    for i in range(3):
        Image.new('RGBA', (40, 60), 'blue').save(source/f'B{i}-1-T-Black-M-NO1-1.png', dpi=(25.4,25.4))
    worker = GenerateWorker(None, source, tmp_path/'out', 'JOB', LayoutSettings(
        dpi=25.4, cutter_mode='dual', cutter_auto_knife=True, number_images=False))
    updates, finished, failures = [], [], []
    scan_events = []
    worker.sources_ready.connect(lambda _paths: scan_events.append('来源已扫描'))
    worker.analysis_ready.connect(lambda report: scan_events.append(report['stage']))
    worker.timings_ready.connect(updates.append)
    worker.finished.connect(lambda output, result: finished.append(result))
    worker.failed.connect(failures.append)
    worker.run()
    assert not failures
    assert scan_events[:2] == ['来源已扫描', '文件名分析']
    result = finished[0]['operation_timings']
    names = [row['name'] for row in result['steps']]
    assert names[0] == '扫描文件名'
    assert {'读取尺寸与标签', '刀位与排版计算',
            '分段合成、安全检查与保存'} <= set(names)
    part_steps = {step['name'] for part in finished[0]['parts']
                  for step in part['operation_timings']['steps']}
    assert {'图片准备与合成', '合成像素安全检查',
            '膜标签与辅助线处理', '保存输出图片'} <= part_steps
    assert abs(sum(s['seconds'] for s in result['steps'])-result['total_seconds']) < .01
    assert result['status'] == '已完成'
    assert updates[-1] == result
    assert worker.output == tmp_path/'切膜机文件'
    assert not list(worker.output.glob('*.json'))
    report = next((tmp_path/'排版日志').glob('*_排版报告*.txt')).read_text(encoding='utf-8')
    assert '扫描文件名' in report and '最耗时步骤' in report
    assert '耗时与并行处理' in report
    assert '输出文件信息' in report
    assert 'PNG · RGBA · 每通道 8 位' in report
    assert '文件大小：' in report
    assert finished[0]['alpha_channel']
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


def test_running_phase_is_highlighted_first_without_changing_measurements():
    bridge = MainWindowWorkerBridge()
    panel = OperationTimingPanel(bridge)
    OWNERS.extend((bridge, panel))
    timer = OperationTiming()
    timer.phase('扫描文件名')
    timer.phase('读取尺寸与标签')
    timer.phase('保存输出图片')
    snapshot = timer.snapshot()
    original = [s['name'] for s in snapshot['steps']]
    panel.receive(snapshot)
    assert panel.table.item(0,0).text() == '保存输出图片'
    assert panel.table.item(0,0).font().bold()
    assert '进行中' in panel.table.item(0,2).text()
    assert '当前：保存输出图片' in panel.summary.text()
    assert [s['name'] for s in snapshot['steps']] == original
    assert [panel.table.item(i,0).text() for i in (1,2)] == original[:2]
    panel.receive(timer.finish())
    assert [panel.table.item(i,0).text() for i in range(3)] == original
    assert not panel.table.item(0,0).font().bold()
    assert '当前：' not in panel.summary.text()
    panel.reset()
    assert panel.display_phase is None
    panel.close()


def test_copy_timing_includes_output_file_metadata():
    from test_output_file_info import record
    from automatic_print.layout_engine.output.output_file_info import result_file_report
    bridge = MainWindowWorkerBridge()
    panel = OperationTimingPanel(bridge)
    OWNERS.extend((bridge, panel))
    panel.save_report_provider = lambda: result_file_report(record())
    panel.copy_report()
    assert '600.00 MB' in APP.clipboard().text()
    assert 'PNG · RGBA' in APP.clipboard().text()
    assert '压缩等级：1' in APP.clipboard().text()
    panel.close()
