"""Developer-only, read-only DTF source sampling and cold batch timing."""

from __future__ import annotations

import json
import os
import random
import re
from threading import Lock
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from automatic_print.layout_engine.intake.discovery.batch_discovery import scan_batches
from .benchmark_report import format_report


_BATCH_NAME = re.compile(r"\d{12}")
_DATE_NAME = re.compile(r"\d{4}")
_HL_NAMES = frozenset({"HL", "HL 2"})
_EMIT_LOCK = Lock()


def haloo_roots(root: Path) -> list[Path]:
    """Locate explicit HL source roots without traversing unrelated platforms."""
    root = Path(root)
    if root.name.upper() in _HL_NAMES:
        return [root]
    children = [item for item in root.iterdir() if item.is_dir()]
    direct = [item for item in children if item.name.upper() in _HL_NAMES]
    if direct:
        return sorted(direct)
    dates = [item for item in children if _DATE_NAME.fullmatch(item.name)]
    return sorted(platform for date in dates for platform in date.iterdir()
                  if platform.is_dir() and platform.name.upper() in _HL_NAMES)


def choose_batches(root: Path, count: int, seed: int, progress=None):
    candidates, scan_errors, directories = [], [], 0
    for platform_root in haloo_roots(root):
        if progress:
            progress("扫描平台", platform_root)
        scan = scan_batches(platform_root)
        directories += scan["directories"]
        scan_errors.extend(scan["errors"])
        candidates.extend(batch for batch in scan["batches"]
                          if _BATCH_NAME.fullmatch(batch["folder"].name)
                          and "排版日志" not in batch["folder"].parts)
    candidates.sort(key=lambda item: str(item["folder"]).casefold())
    if len(candidates) < count:
        raise ValueError(f"DTF 盘只发现 {len(candidates)} 个可读 HL 批次，无法随机抽取 {count} 个")
    return random.Random(seed).sample(candidates, count), {
        "candidate_count": len(candidates), "scanned_directories": directories,
        "scan_errors": scan_errors,
    }


def _emit(event: str, **details) -> None:
    with _EMIT_LOCK:
        print(json.dumps({"event": event, **details}, ensure_ascii=False), flush=True)


def _write_report(path: Path, report: dict) -> None:
    temporary = path.with_name(path.name + ".未完成")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    readable = path.with_suffix(".txt")
    temporary_text = readable.with_name(readable.name + ".未完成")
    temporary_text.write_text(format_report(report), encoding="utf-8")
    temporary_text.replace(readable)


def run(root: Path, output: Path, settings_data: dict, count=10, seed=None):
    """Generate sampled batches one at a time with a fresh cache per batch."""
    from PySide6.QtCore import Qt
    from automatic_print.layout_engine.domain.models import LayoutSettings
    from automatic_print.layout_engine.output.output_name import batch_output_directory
    from automatic_print.ui.workers import GenerateWorker

    root, output = Path(root), Path(output)
    if output.exists():
        raise ValueError(f"测试目录已存在，为防止覆盖请另选新目录：{output}")
    if not root.is_dir():
        raise ValueError(f"DTF 来源目录不存在：{root}")
    if str(output).upper().startswith("Z:\\") or str(output).casefold().startswith(
        "\\\\192.168.11.28\\dtf".casefold()
    ):
        raise ValueError("测试结果不能写入 DTF 盘")
    output.mkdir(parents=True)
    settings_data = dict(settings_data)
    for name in ("force_small_pair_sizes", "dimension_overrides", "header_gap_overrides",
                 "width_adjustments", "manual_rotations", "sequence_numbers"):
        if name in settings_data:
            settings_data[name] = tuple(settings_data[name])
    settings = replace(LayoutSettings(**settings_data), platform_name="Haloo")
    if settings.output_format.lower() != "png":
        settings = replace(settings, output_format="png")
    seed = random.SystemRandom().getrandbits(64) if seed is None else int(seed)
    report = {"source_root": str(root), "output_root": str(output),
              "seed": seed, "sample_count": count, "cache_policy": "每批独立空缓存；未清空系统文件缓存",
              "settings": asdict(settings), "batches": [], "status": "扫描中"}
    report_path = output / "冷启动10批耗时.json"
    _write_report(report_path, report)
    started = perf_counter()
    try:
        selected, scan = choose_batches(root, count, seed,
                                        lambda stage, folder: _emit("scan", stage=stage, folder=str(folder)))
    except Exception as error:
        report.update(status="扫描失败", scan_seconds=round(perf_counter() - started, 3), error=str(error))
        _write_report(report_path, report)
        _emit("failed", error=str(error), report=str(report_path))
        return report
    report.update(scan, scan_seconds=round(perf_counter() - started, 3),
                  selected=[{"folder": str(item["folder"]), "images": item["image_count"]}
                            for item in selected], status="生成中")
    _write_report(report_path, report)
    for index, batch in enumerate(selected, 1):
        folder = batch["folder"]
        cache = output / "cache" / f"{index:02d}"
        if cache.exists():
            raise ValueError(f"批次缓存不是空目录：{cache}")
        cache.mkdir(parents=True)
        os.environ["LOCALAPPDATA"] = str(cache)
        job = f"BENCH_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:8]}"
        destination = batch_output_directory(output, folder.name, job)
        worker = GenerateWorker(batch["images"], folder, destination, job, settings,
                                batch_name=folder.name)
        worker._save_history = lambda _result: None
        done, failures, timing = [], [], []
        previous_stage = [None]
        def on_progress(stage, current, total, detail):
            if stage != previous_stage[0]:
                previous_stage[0] = stage
                _emit("progress", index=index, count=count, folder=str(folder),
                      stage=stage, current=current, total=total, detail=detail)
        def on_timing(data):
            timing.append(data)
            _emit("timing", index=index, data=data)
        worker.progress.connect(on_progress, Qt.ConnectionType.DirectConnection)
        worker.timings_ready.connect(on_timing, Qt.ConnectionType.DirectConnection)
        worker.finished.connect(lambda path, result: done.append((path, result)), Qt.ConnectionType.DirectConnection)
        worker.failed.connect(failures.append, Qt.ConnectionType.DirectConnection)
        batch_started = perf_counter()
        _emit("batch_started", index=index, count=count, folder=str(folder), images=batch["image_count"])
        try:
            worker.run()
        except KeyboardInterrupt:
            report.update(status="已停止", completed=sum(
                item["status"] == "已完成" for item in report["batches"]),
                failed=sum(item["status"] == "失败" for item in report["batches"]),
                total_seconds=round(perf_counter() - started, 3),
                interrupted={"index": index, "folder": str(folder),
                             "images": batch["image_count"]})
            _write_report(report_path, report)
            _emit("stopped", index=index, folder=str(folder), report=str(report_path))
            return report
        item = {"index": index, "folder": str(folder), "images": batch["image_count"],
                "cache_directory": str(cache), "worker_threads": settings.worker_threads,
                "wall_seconds": round(perf_counter() - batch_started, 3),
                "cumulative_seconds": round(perf_counter() - started, 3),
                "operation_timings": timing[-1] if timing else None}
        if done:
            path, result = done[0]
            item.update(status="已完成", output=path, files=result.get("files", []),
                        engine_timings=result.get("timings_seconds", {}),
                        output_bytes=result.get("file_size_bytes", 0))
        else:
            item.update(status="失败", error=failures[0] if failures else "批次未返回结果")
        report["batches"].append(item)
        _write_report(report_path, report)
        _emit("batch_finished", **{key: item[key] for key in
              ("index", "folder", "status", "wall_seconds", "cumulative_seconds")})
    report.update(total_seconds=round(perf_counter() - started, 3),
                  completed=sum(item["status"] == "已完成" for item in report["batches"]),
                  failed=sum(item["status"] == "失败" for item in report["batches"]))
    report["status"] = "已完成" if report["failed"] == 0 else "部分失败"
    _write_report(report_path, report)
    _emit("finished", status=report["status"], completed=report["completed"],
          failed=report["failed"], total_seconds=report["total_seconds"], report=str(report_path))
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--settings", type=Path)
    source.add_argument("--settings-json")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    settings = json.loads(args.settings_json) if args.settings_json else json.loads(
        args.settings.read_text(encoding="utf-8"))
    result = run(args.root, args.output, settings, args.count, args.seed)
    return 0 if result.get("status") == "已完成" else 1


if __name__ == "__main__":
    raise SystemExit(main())
