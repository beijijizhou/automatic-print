"""Download generated S2B production-image exports through the logged-in site."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zipfile import ZipFile

from ...chrome_session import connect_debug_chrome, open_authenticated_page
from ...batch_downloads import PRODUCTION_IMAGE_EXTENSIONS


EXPORT_URL = "https://overseasfactory.s2bdiy.com/factory/exportRecord"


@dataclass(frozen=True)
class S2BExportRecord:
    record_id: int
    batch_number: str
    image_count: int
    created_at: str
    ready: bool
    download_url: str
    archive_name: str


def parse_export_rows(payload: dict) -> list[S2BExportRecord]:
    data = payload.get("data") if isinstance(payload, dict) else None
    rows = data.get("data", ()) if isinstance(data, dict) else ()
    records = []
    for row in rows:
        params = row.get("params") if isinstance(row.get("params"), dict) else {}
        batch = str(params.get("批次号") or "").strip()
        if not batch or int(row.get("type") or 0) != 4:
            continue
        file_info = row.get("oss_file") if isinstance(row.get("oss_file"), dict) else {}
        records.append(S2BExportRecord(
            record_id=int(row.get("id") or 0),
            batch_number=batch,
            image_count=int(row.get("export_success_num") or row.get("export_num") or 0),
            created_at=str(row.get("created_at") or ""),
            ready=int(row.get("status") or 0) == 2 and bool(row.get("download_url")),
            download_url=str(row.get("download_url") or ""),
            archive_name=Path(str(file_info.get("origin_name") or f"{batch}.zip")).name,
        ))
    return records


def list_s2b_batches(progress=None):
    from .production import list_s2b_production_batches
    with _authenticated_page(progress) as page:
        return list_s2b_production_batches(page)


def download_s2b_exports(batch_numbers, output_root: Path, progress=None) -> list[Path]:
    if not batch_numbers:
        raise ValueError("请至少选择一个 S2B 生产图批次。")
    batches = list(dict.fromkeys(batch_numbers))
    saved = {
        batch: existing
        for batch in batches
        if (existing := _existing_batch(output_root, batch))
    }
    pending = [batch for batch in batches if batch not in saved]
    for index, batch in enumerate(batches, 1):
        if batch in saved:
            _report(progress, f"[{index}/{len(batches)}] 本地已有 S2B / {batch}，跳过下载")
    if not pending:
        return [saved[batch] for batch in batches]
    with _authenticated_page(progress) as page:
        from .production import wait_for_ready_exports
        selected = wait_for_ready_exports(page, pending, progress)
        total = len(selected)
        for index, record in enumerate(selected, 1):
            archive = _download_archive(record, output_root, index, total, progress)
            saved[record.batch_number] = _extract_archive(
                archive, output_root, record.batch_number
            )
            _api(page, "POST", "/factory/userExportRecord/downloadRecord", {"id": record.record_id})
            _report(progress, f"[{index}/{total}] 已下载并解压 S2B / {record.batch_number}")
        return [saved[batch] for batch in batches]


def _latest_exports(page):
    latest = {}
    for record in _records_from_page(page):
        latest.setdefault(record.batch_number, record)
    return latest


class _authenticated_page:
    def __init__(self, progress): self.progress = progress
    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self.playwright = sync_playwright().start()
        self.browser = connect_debug_chrome(self.playwright, EXPORT_URL)
        self.page = open_authenticated_page(
            self.browser, EXPORT_URL, ".exportRecordBlock", progress=self.progress
        )
        return self.page
    def __exit__(self, *_exc):
        self.playwright.stop()


def _records_from_page(page):
    query = ("/factory/userExportRecord?page=1&per_page=100&type=4&is_download="
             "&status=&batch_number=&created_at_before=&created_at_after=")
    return parse_export_rows(_api(page, "GET", query))


def _api(page, method, path, payload=None):
    result = page.evaluate("""async ({method, path, payload}) => {
      const saved = localStorage.getItem('pro__Access-Token');
      if (!saved) throw new Error('S2B 登录已失效，请重新登录');
      let token = saved;
      try { const parsed = JSON.parse(saved); token = parsed.value || parsed; } catch (_) {}
      const response = await fetch('/req' + path, {
        method,
        credentials: 'same-origin',
        headers: {'Accept':'application/json', 'Content-Type':'application/json;charset=UTF-8',
                  'Authorization':'Bearer ' + token},
        body: payload == null ? undefined : JSON.stringify(payload)
      });
      const result = await response.json();
      if (!response.ok || result.status_code !== 200) {
        throw new Error(result.msg || ('S2B 接口返回 ' + response.status));
      }
      return result;
    }""", {"method": method, "path": path, "payload": payload})
    return result


def _download_archive(record, output_root, index, total, progress):
    host = urlsplit(record.download_url).netloc.lower()
    trusted_host = host == "s2bdiy.com" or host.endswith(".s2bdiy.com")
    if not record.download_url.startswith("https://") or not trusted_host:
        raise RuntimeError(f"S2B 批次 {record.batch_number} 返回了不受信任的下载地址。")
    folder = output_root / "S2B" / "ARCHIVES"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{record.batch_number}_{record.archive_name}"
    partial = target.with_suffix(target.suffix + ".未完成")
    request = Request(record.download_url, headers={"User-Agent": "AutomaticPrint/1"})
    try:
        with urlopen(request, timeout=120) as response, partial.open("wb") as stream:
            expected = int(response.headers.get("Content-Length") or 0)
            written = 0
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
                written += len(chunk)
                percent = f" · {written / expected:.0%}" if expected else ""
                _report(progress, f"[{index}/{total}] 正在下载 S2B / {record.batch_number}{percent}")
        partial.replace(target)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return target


def _extract_archive(archive, output_root, batch_number):
    destination = output_root / "S2B" / "BATCHES"
    destination.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive) as bundle:
        root = destination.resolve()
        members = bundle.infolist()
        for member in members:
            target = (destination / member.filename).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError(f"S2B 压缩包包含不安全路径：{member.filename}")
        corrupt = bundle.testzip()
        if corrupt:
            raise RuntimeError(f"S2B 压缩包损坏：{corrupt}")
        bundle.extractall(destination)
        roots = {Path(member.filename).parts[0] for member in members if member.filename}
    if len(roots) == 1 and (destination / next(iter(roots))).is_dir():
        return destination / next(iter(roots))
    return destination / batch_number


def _existing_batch(output_root, batch_number):
    root = output_root / "S2B" / "BATCHES"
    if not root.is_dir(): return None
    for folder in root.iterdir():
        if folder.is_dir() and batch_number in folder.name and any(
            path.suffix.lower() in PRODUCTION_IMAGE_EXTENSIONS for path in folder.rglob("*")
        ):
            return folder
    return None


def _report(progress, message):
    if progress: progress(message)
