import json

from automatic_print.diagnostics.random_dtf import choose_batches, haloo_roots


def test_random_selection_uses_complete_hl_batches_only(tmp_path):
    platform = tmp_path / "0919" / "HL"
    for number in range(12):
        batch = platform / f"609192100{number:03d}"
        batch.mkdir(parents=True)
        (batch / "image.png").write_bytes(b"test")
    generated = platform / "切膜机文件" / "609192100999"
    generated.mkdir(parents=True)
    (generated / "output.png").write_bytes(b"test")
    other = tmp_path / "0919" / "LF" / "609192100998"
    other.mkdir(parents=True)
    (other / "other.png").write_bytes(b"test")

    assert haloo_roots(tmp_path) == [platform]
    selected, scan = choose_batches(tmp_path, 10, seed=123)
    repeated, _ = choose_batches(tmp_path, 10, seed=123)
    assert len(selected) == len({item["folder"] for item in selected}) == 10
    assert [item["folder"] for item in selected] == [item["folder"] for item in repeated]
    assert scan["candidate_count"] == 12
    assert all(item["folder"].parent == platform for item in selected)


def test_random_selection_requires_ten_valid_batches(tmp_path):
    platform = tmp_path / "HL"
    platform.mkdir()
    for index in range(9):
        batch = platform / f"609192100{index:03d}"
        batch.mkdir()
        (batch / "image.png").write_bytes(b"test")
    import pytest

    with pytest.raises(ValueError, match="只发现 9 个"):
        choose_batches(platform, 10, seed=1)


def test_cold_report_keeps_each_batch_and_continues_after_failure(tmp_path, monkeypatch, capsys):
    from dataclasses import asdict
    from PySide6.QtCore import QObject, Signal
    from automatic_print.diagnostics.random_dtf import run
    from automatic_print.layout_engine.domain.models import LayoutSettings
    import automatic_print.ui.workers as workers

    root = tmp_path / "HL"
    for index in range(2):
        batch = root / f"609192100{index:03d}"
        batch.mkdir(parents=True)
        (batch / "image.png").write_bytes(b"test")

    class FakeWorker(QObject):
        progress = Signal(str, object, object, str)
        timings_ready = Signal(object)
        finished = Signal(str, object)
        failed = Signal(str)

        def __init__(self, images, source, output, job, settings, batch_name):
            super().__init__()
            self.source, self.output = source, output

        def run(self):
            self.progress.emit("扫描文件夹", 1, 1, str(self.source))
            self.timings_ready.emit({"total_seconds": 0.1, "steps": []})
            if self.source.name.endswith("000"):
                self.failed.emit("sample failure")
            else:
                self.finished.emit(str(self.output), {
                    "files": ["sample.png"], "timings_seconds": {"saving_png": 0.1},
                    "file_size_bytes": 42,
                })

    monkeypatch.setattr(workers, "GenerateWorker", FakeWorker)
    report = run(root, tmp_path / "out", asdict(LayoutSettings()), count=2, seed=7)
    assert report["completed"] == report["failed"] == 1
    assert len(report["batches"]) == 2
    assert all(item["operation_timings"] for item in report["batches"])
    assert len({item["cache_directory"] for item in report["batches"]}) == 2
    assert (tmp_path / "out" / "冷启动10批耗时.json").is_file()
    readable = (tmp_path / "out" / "冷启动10批耗时.txt").read_text(encoding="utf-8")
    assert "本批完整耗时" in readable and "sample failure" in readable
    assert "本次随机抽中的批次" in readable
    assert readable.count("张 · ") >= 2
    assert json.loads((tmp_path / "out" / "冷启动10批耗时.json").read_text(encoding="utf-8"))[
        "status"] == "部分失败"
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len([event for event in events if event['event'] == 'timing']) == 2


def test_stopped_random_batch_keeps_completed_result_and_selected_list(
        tmp_path, monkeypatch, capsys):
    from dataclasses import asdict
    from PySide6.QtCore import QObject, Signal
    from automatic_print.diagnostics.random_dtf import run
    from automatic_print.layout_engine.domain.models import LayoutSettings
    import automatic_print.ui.workers as workers

    root = tmp_path / "HL"
    for index in range(2):
        batch = root / f"609192100{index:03d}"
        batch.mkdir(parents=True)
        (batch / "image.png").write_bytes(b"test")

    class FakeWorker(QObject):
        progress = Signal(str, object, object, str)
        timings_ready = Signal(object)
        finished = Signal(str, object)
        failed = Signal(str)
        calls = 0

        def __init__(self, images, source, output, job, settings, batch_name):
            super().__init__()
            self.source, self.output = source, output

        def run(self):
            type(self).calls += 1
            if type(self).calls == 1:
                self.finished.emit(str(self.output), {"files": ["sample.png"]})
            else:
                raise KeyboardInterrupt

    monkeypatch.setattr(workers, "GenerateWorker", FakeWorker)
    report = run(root, tmp_path / "out", asdict(LayoutSettings()), count=2, seed=7)
    assert report["status"] == "已停止"
    assert report["completed"] == 1 and report["failed"] == 0
    assert len(report["selected"]) == 2 and len(report["batches"]) == 1
    assert report["interrupted"]["index"] == 2
    readable = (tmp_path / "out" / "冷启动10批耗时.txt").read_text(encoding="utf-8")
    assert "本次随机抽中的批次" in readable and "未计为成功" in readable
    assert any(json.loads(line)["event"] == "stopped" for line in capsys.readouterr().out.splitlines())


def test_benchmark_dialog_shows_live_phase_timing():
    from time import perf_counter
    from PySide6.QtWidgets import QApplication, QWidget
    from automatic_print.ui.cold_batch_benchmark import ColdBatchBenchmarkDialog

    app = QApplication.instance() or QApplication([])
    owner = QWidget()
    dialog = ColdBatchBenchmarkDialog(owner)
    dialog._started_at = perf_counter() - 2
    snapshot = {
        'status': '运行中', 'total_seconds': 1.5, 'captured_at': 0,
        'active_phase': '标签与刀码测量',
        'steps': [{'name': '标签与刀码测量', 'seconds': 1.5, 'running': True}],
    }
    events = [
        {'event': 'batch_started', 'index': 1, 'count': 10,
         'folder': '609181334053', 'images': 125},
        {'event': 'timing', 'index': 1, 'data': snapshot},
    ]

    class Output:
        def readAllStandardOutput(self):
            return '\n'.join(json.dumps(event, ensure_ascii=False) for event in events).encode() + b'\n'

    dialog.process = Output()
    dialog._read_output()
    assert '当前批次' in dialog.elapsed.text()
    assert '标签与刀码测量' in dialog.timing_panel.summary.text()
    assert dialog.timing_panel.table.item(0, 1).text().endswith('秒')
    events[:] = [
        {'event': 'timing', 'index': 1, 'data': dict(snapshot, status='已完成',
            steps=[{'name': '标签与刀码测量', 'seconds': 2.0, 'running': False}])},
        {'event': 'batch_finished', 'index': 1, 'status': '已完成',
         'wall_seconds': 2.0, 'cumulative_seconds': 2.1},
    ]
    dialog._read_output()
    assert '标签与刀码测量：2.00 秒' in dialog.log.toPlainText()
    dialog.timing_panel.timer.stop()
    dialog.process = None
    dialog.close()
    owner.close()
