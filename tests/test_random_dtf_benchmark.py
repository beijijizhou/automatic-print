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


def test_cold_report_keeps_each_batch_and_continues_after_failure(tmp_path, monkeypatch):
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
    assert json.loads((tmp_path / "out" / "冷启动10批耗时.json").read_text(encoding="utf-8"))[
        "status"] == "部分失败"
