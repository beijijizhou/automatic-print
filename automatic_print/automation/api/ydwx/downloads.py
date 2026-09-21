"""Download selected SDS manuscripts under verified production-task names."""

from pathlib import Path
from zipfile import BadZipFile, ZipFile

from automatic_print.layout_engine.output.output_name import label_output_name

from .batches import YdwxBatch, list_batches
from .gateway import request_gateway


def download_batches(selected, output_root, progress=None):
    """Keep each selected task independent; never treat partial exports as complete."""
    current = {row.task_id: row for row in list_batches()}
    saved, failures = [], []
    for index, original in enumerate(selected, 1):
        live = current.get(original.task_id)
        try:
            if live is None or (
                live.name, live.number, live.manuscript_count
            ) != (
                original.name, original.number, original.manuscript_count
            ):
                raise ValueError("批次名称、编号或稿件总数已变化；请刷新列表后重新选择。")
            if live.manuscript_count <= 0:
                raise ValueError("平台尚无可下载稿件。")
            if not 0 <= live.downloaded_count <= live.manuscript_count:
                raise ValueError("平台稿件已下载数异常；请刷新后核对。")
            remaining = live.manuscript_count - live.downloaded_count
            request_count = live.manuscript_count if remaining == 0 else remaining
            if request_count > 600:
                raise ValueError(
                    f"本次需下载 {request_count} 条；平台单次上限 600 条，"
                    "请在平台筛选或使用官方下载助手。"
                )
            if progress:
                progress(f"[{index}/{len(selected)}] 正在下载 {live.name}")
            path = download_batch(live, Path(output_root))
            saved.append((live, path))
            if progress:
                progress(f"[{index}/{len(selected)}] 已保存 {live.name}：{path}")
        except Exception as error:
            failures.append((original.name, str(error)))
            if progress:
                progress(f"[{index}/{len(selected)}] {original.name} 未完成：{error}")
    return saved, failures


def download_batch(batch: YdwxBatch, output_root):
    """The site's own download action uses down for missing, redown for all-down."""
    mode = "redown" if batch.downloaded_count == batch.manuscript_count else "down"
    folder_name = Path(label_output_name(f"{batch.name}_{batch.number}_{batch.task_id}")).stem
    folder = output_root / "亿点万象" / "BATCHES" / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / ("完整稿件.zip" if mode == "redown" else "新增稿件.zip")
    pending = folder / (target.name + ".未完成")
    if target.exists() or pending.exists():
        raise FileExistsError(f"本地已有 {target.name} 或未完成文件；未覆盖，请先核对。")
    try:
        with request_gateway({"action": "download", "task_id": batch.task_id, "mode": mode}) as response, pending.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        with ZipFile(pending) as archive:
            names = [item.filename for item in archive.infolist() if not item.is_dir()]
            if not names or archive.testzip() is not None:
                raise ValueError("返回的 ZIP 为空或损坏。")
            for name in names:
                member = Path(name)
                if member.is_absolute() or ".." in member.parts:
                    raise ValueError(f"ZIP 包含不安全路径：{name}")
        pending.replace(target)
    except (OSError, RuntimeError) as error:
        raise RuntimeError(
            f"{batch.name} 下载连接失败；保留未完成文件：{pending}"
        ) from error
    except (BadZipFile, ValueError) as error:
        raise ValueError(f"{batch.name} 下载内容未通过 ZIP 校验；保留未完成文件：{pending}") from error
    return target
