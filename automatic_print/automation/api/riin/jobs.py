"""Run verified RIIN file-output jobs outside the GUI thread."""
import json
from pathlib import Path
import tempfile
import time
import uuid

from .elevation import launch_elevated


def available_prn_path(folder, stem=None):
    root = Path(folder).resolve()
    candidate = root / f"{stem or root.name}.prn"
    index = 2
    while candidate.exists():
        candidate = root / f"{stem or root.name}-{index}.prn"
        index += 1
    return candidate


def generated_pngs(folder, result):
    root = Path(folder).resolve()
    names = result.get("files") or [result["filename"]]
    files = [(root / name).resolve() for name in names]
    missing = [path for path in files if not path.is_file()]
    if not files or missing:
        raise ValueError(
            "本地排版没有返回可导入的最终PNG。"
            if not files
            else f"本地排版结果不存在：{missing[0]}"
        )
    if any(path.suffix.lower() != ".png" for path in files):
        raise ValueError("RIIN自动化只接受本地排版生成的PNG。")
    return files


def _print_groups(result, route):
    parts = route.get('parts') or []
    if not parts:
        return [(route.get('folder', ''), result.get('files') or [result['filename']])]
    names = result.get('files') or [result['filename']]
    if [part['filename'] for part in parts] != names:
        raise ValueError('分区归档清单与实际输出文件顺序不一致，禁止导入RIIN。')
    groups = []
    for part in parts:
        key = (part['folder'], tuple(part['knife_signature']))
        if not groups or groups[-1][0] != key:
            groups.append((key, []))
        groups[-1][1].append(part['filename'])
    return [(key[0], files) for key, files in groups]


def generate_prn(files, output, progress):
    paths = [Path(path).resolve(strict=True) for path in files]
    target = Path(output).resolve()
    if not paths or any(path.suffix.lower() != ".png" for path in paths):
        raise ValueError("RIIN导入清单必须包含已生成的PNG。")
    folder = Path(tempfile.gettempdir()) / "AutomaticPrint" / "riin-reports"
    folder.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    manifest = folder / f"{token}-files.json"
    report = folder / f"{token}-result.json"
    manifest.write_text(
        json.dumps([str(path) for path in paths], ensure_ascii=False),
        encoding="utf-8",
    )
    started = time.monotonic()
    finished = False
    last_status = ''
    try:
        launch_elevated([
            "automate-layout", "--report", str(report),
            "--manifest", str(manifest), "--output", str(target),
        ])
        while True:
            active_status = False
            if report.is_file():
                try:
                    payload = json.loads(report.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    pass
                else:
                    if payload.get('done', True):
                        finished = True
                        break
                    active_status = True
                    status = str(payload.get('status') or '').strip()
                    if status and status != last_status:
                        progress(status)
                        last_status = status
            elapsed = time.monotonic() - started
            if elapsed > 7500:
                raise TimeoutError(
                    f"RIIN任务超过125分钟仍未返回；任务未被取消：{target}"
                )
            if active_status:
                time.sleep(0.5)
                continue
            if target.is_file():
                progress(
                    f"RIIN正在生成 {target.name} · "
                    f"{target.stat().st_size / 1_000_000_000:.2f} GB · "
                    f"{elapsed:.0f} 秒"
                )
            else:
                progress(
                    f"RIIN正在导入 {len(paths)} 个排版PNG · {elapsed:.0f} 秒"
                )
            time.sleep(0.5)
        if not payload.get("ok"):
            raise RuntimeError(payload.get("error") or "RIIN生成PRN失败。")
        automation = payload.get("automation") or {}
        if automation.get("state") != "completed":
            raise RuntimeError("RIIN没有返回完整的文件生成结果。")
        return automation
    finally:
        if finished or not report.is_file():
            manifest.unlink(missing_ok=True)
        if finished:
            report.unlink(missing_ok=True)


def generate_batch_prns(processed, progress, stop_requested=lambda: False):
    output_root = Path(processed["output_folder"])
    completed, errors, skipped = [], [], []
    batches = processed.get("batches") or []
    routes = processed.get('batch_routes') or {}
    for index, (batch, result) in enumerate(batches, start=1):
        if stop_requested():
            skipped.extend(name for name, _result in batches[index - 1:])
            break
        try:
            groups = _print_groups(result, routes.get(batch, {'folder': batch}))
        except Exception as error:
            errors.append({"batch": batch, "error": str(error)})
            progress(f"{batch}：分区清单不安全，未导入RIIN · {error}")
            continue
        for segment, (relative, names) in enumerate(groups, 1):
            if stop_requested():
                skipped.extend(name for name, _result in batches[index - 1:])
                return completed, errors, skipped
            try:
                folder = output_root / relative
                files = generated_pngs(folder, {'files': names})
                output = available_prn_path(folder, batch)
                progress(f"[{index}/{len(batches)}] {batch} · 第{segment}/{len(groups)}组：正在交给RIIN生成PRN")
                automation = generate_prn(
                    files, output,
                    lambda message: progress(
                        f"[{index}/{len(batches)}] {batch} · {message}"
                    ),
                )
                completed.append({"batch": batch, "folder": relative,
                                  "files": names, **automation})
                status = ('PRN已生成并加入PrintExp' if automation.get('riin_complete', True)
                          else 'RIIN已开始写入，PRN已加入PrintExp；文件仍在生成')
                progress(f"[{index}/{len(batches)}] {batch} · 第{segment}/{len(groups)}组：{status}")
            except Exception as error:
                detail = (f'第{segment}/{len(groups)}组 {relative}：{error}'
                          if len(groups) > 1 else str(error))
                errors.append({"batch": batch, "error": detail})
                progress(f"{batch}：PRN生成失败，继续处理其他安全分区 · {detail}")
    return completed, errors, skipped
