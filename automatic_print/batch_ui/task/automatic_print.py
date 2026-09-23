"""Continue a completed platform download through layout and RIIN output."""
from pathlib import Path

from ...automation.batches.naming import save_batch_type


def save_downloaded_batch_types(output, platform_name, batch_types):
    platform_root = Path(output) / platform_name
    for batch_number, batch_type in batch_types.items():
        standard = platform_root / "BATCHES" / batch_number
        if standard.is_dir():
            save_batch_type(standard, batch_type)
            continue
        matches = [
            folder for folder in platform_root.rglob(batch_number)
            if folder.is_dir() and folder.name == batch_number
        ]
        if len(matches) == 1:
            save_batch_type(matches[0], batch_type)


def process_and_print(process, files, progress, stop_requested):
    progress("下载与解压完成；正在使用本地排版参数生成最终PNG。")
    processed = process()
    progress("最终PNG排版完成；正在核对安全分区并准备RIIN任务。")
    from ...automation.api.riin.jobs import generate_batch_prns

    printed, errors, skipped = generate_batch_prns(
        processed, progress, stop_requested
    )
    progress(
        f"RIIN任务处理完成：{len(printed)} 个PRN成功，"
        f"{len(errors)} 个失败，{len(skipped)} 个停止前未提交。"
    )
    processed.update(
        type="downloaded_processed_and_printed",
        files=files,
        print_files=printed,
        print_errors=errors,
        skipped_print_batches=skipped,
    )
    return processed
