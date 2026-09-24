"""Execute one claimed command through the existing safe production workflow."""

from dataclasses import fields, replace
from pathlib import Path

from PySide6.QtCore import QSettings

from ....layout_engine import LayoutSettings
from ....batch_ui.local.processing import process_local_batches
from ....batch_ui.task.automatic_print import save_downloaded_batch_types
from ...browser.batches import (
    download_selected_batches, load_batch_records, load_batch_records_between,
)
from ..machine_status.commands import get_command, update_command
from .lifecycle import CommandLifecycle, CommandProgress


def run_command(command_id):
    progress = CommandProgress(command_id)
    action = "download_layout"
    lifecycle = None
    try:
        command = get_command(command_id)
        action = str(command.get("action") or "download_layout")
        payload = command.get("payload") or {}
        if action == "probe":
            result = inspect_machine()
            update_command(
                command_id, "succeeded", phase="目标机实时检测通过",
                progress_percent=100, result=result,
            )
            return 0
        if action == "source_update":
            from .source_update import execute_source_update, schedule_monitor_restart
            result = execute_source_update(command.get("payload") or {}, progress)
            update_command(
                command_id, "succeeded",
                phase=f"源码{'回滚' if result.get('rollback') else '更新'}完成，等待程序安全重启",
                progress_percent=100, result=result,
            )
            schedule_monitor_restart()
            return 0
        lifecycle = CommandLifecycle(
            command_id, action, payload, publish=update_command,
        )
        replayed = lifecycle.begin()
        if replayed is not None:
            return replayed
        if action in {"start_print", "pause_print", "clean_resume"}:
            result = execute_printer_action(action, progress, payload)
            phase = {
                "start_print": "PrintExp 已开始打印",
                "pause_print": "PrintExp 已暂停",
                "clean_resume": "清洗完成，已继续打印",
            }[action]
            lifecycle.succeed(phase, result)
            return 0
        progress("正在准备远程下载排版任务", force=True)
        result = execute_download_layout(payload, progress)
        errors = [
            str(item.get("error") if isinstance(item, dict) else item).strip()
            for item in result.get("prn_errors") or []
            if str(item.get("error") if isinstance(item, dict) else item).strip()
        ]
        if errors:
            lifecycle.fail("PRN生成或装载失败", "；".join(errors)[:2000], result)
            return 1
        lifecycle.succeed("远程下载排版完成", result)
        return 0
    except Exception as error:
        try:
            phase = (
                "目标机实时检测失败" if action == "probe" else
                "源码更新失败" if action == "source_update" else
                "打印机控制失败" if action != "download_layout" else
                "远程下载排版失败"
            )
            if lifecycle is not None:
                lifecycle.fail(phase, str(error)[:2000])
            else:
                update_command(
                    command_id, "failed", phase=phase,
                    error_message=str(error)[:2000],
                )
        except Exception:
            pass
        return 1


def inspect_machine():
    from automatic_print import __version__
    from ..machine_status import report_machine
    from ..machine_status.identity import machine_id, machine_name
    from ..printerexp.monitor import PrintExpMonitor

    status = PrintExpMonitor(send=lambda _status: None).collect_status()
    report_machine(status)
    return {
        "machine_id": machine_id(),
        "machine_name": machine_name(),
        "app_version": __version__,
        "source_online": status.get("source_online") is True,
        "status": status,
    }


def execute_printer_action(action, progress, payload=None):
    from ..printerexp.control import clean_then_resume, pause_print, start_print

    if action == "start_print":
        return start_print(
            str((payload or {}).get("expected_batch_name") or ""), progress=progress,
        )
    if action == "pause_print":
        return pause_print(progress=progress)
    if action == "clean_resume":
        return clean_then_resume(progress=progress)
    raise ValueError("不支持的打印机控制指令。")


def execute_download_layout(payload, progress):
    platform = str(payload.get("platform") or "")
    batches = [str(item) for item in payload.get("batch_numbers") or []]
    if not platform or not batches:
        raise ValueError("远程任务缺少平台或批次号。")
    preferences = QSettings("AutomaticPrint", "AutomaticPrint")
    output_text = preferences.value("automation/output_location", "", str).strip()
    if not output_text:
        raise RuntimeError("目标机尚未设置生产批次下载目录。")
    output = Path(output_text)
    output.mkdir(parents=True, exist_ok=True)
    progress("正在核对批次类型与生产图状态", force=True)
    records = _load_selected_records(platform, batches, progress)
    selected = {record.batch_number: record for record in records if record.batch_number in batches}
    missing = [number for number in batches if number not in selected]
    if missing:
        raise RuntimeError("平台没有返回批次：" + "、".join(missing))
    pending = [number for number, record in selected.items() if not record.production_images_ready]
    if pending:
        raise RuntimeError("生产图尚未生成完成：" + "、".join(pending))
    batch_types = {number: selected[number].batch_type for number in batches}
    files = download_selected_batches(platform, batches, output, progress)
    save_downloaded_batch_types(output, platform, batch_types)
    settings = _layout_settings(payload.get("layout_settings") or {}, preferences)
    progress("下载与解压完成；正在生成最终排版 PNG", force=True)
    processed = process_local_batches(
        output, platform, batches, batch_types, settings,
        sample_limit=None, merge_batches=False, progress=progress, preview_only=False,
    )
    printed, errors, skipped = [], [], []
    if payload.get("generate_prn", True):
        progress("排版完成；正在生成 PRN 并加载 PrintExp", force=True)
        from ..riin.jobs import generate_batch_prns
        printed, errors, skipped = generate_batch_prns(processed, progress)
    return {
        "platform": platform,
        "batch_numbers": batches,
        "downloaded_files": len(files),
        "layout_batches": len(processed.get("batches") or []),
        "prn_files": [_printed_name(item) for item in printed],
        "prn_errors": [
            {"batch": str(item.get("batch") or ""), "error": str(item.get("error") or "")[:500]}
            for item in errors
        ],
        "skipped_batches": list(skipped),
        "physical_print_started": False,
    }


def _printed_name(item):
    if isinstance(item, dict):
        return Path(item.get("output") or item.get("path") or item.get("file") or "").name
    return Path(str(item)).name


def _load_selected_records(platform, batches, progress):
    if platform == "S2B":
        return load_batch_records(platform, progress)
    return load_batch_records_between(platform, min(batches), max(batches))


def _layout_settings(values, preferences):
    allowed = {field.name for field in fields(LayoutSettings)}
    clean = {key: value for key, value in dict(values).items() if key in allowed}
    settings = LayoutSettings(**clean)
    machine = preferences.value("layout/machine_number", settings.machine_number, str)
    return replace(settings, machine_number=str(machine).upper())
