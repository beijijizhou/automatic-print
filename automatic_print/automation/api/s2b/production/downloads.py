"""Download generated S2B production-image exports through the logged-in site."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ....browser.session import connect_debug_chrome, open_authenticated_page
from .archive_io import (
    download_archive as _download_archive,
    encoded_download_url as _encoded_download_url,
    existing_batch as _existing_batch,
    extract_archive as _extract_archive,
)


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
    normalized = isinstance(payload, dict) and isinstance(payload.get("records"), list)
    if normalized:
        rows = payload["records"]
    records = []
    for row in rows:
        params = row.get("params") if isinstance(row.get("params"), dict) else {}
        batch = str(row.get("batch_number") if normalized else params.get("批次号") or "").strip()
        if not batch or (not normalized and int(row.get("type") or 0) != 4):
            continue
        file_info = row.get("oss_file") if isinstance(row.get("oss_file"), dict) else {}
        records.append(S2BExportRecord(
            record_id=int((row.get("record_id") if normalized else row.get("id")) or 0),
            batch_number=batch,
            image_count=int((
                row.get("image_count") if normalized else
                row.get("export_success_num") or row.get("export_num") or 0
            ) or 0),
            created_at=str(row.get("created_at") or ""),
            ready=(bool(row.get("ready")) if normalized else
                   int(row.get("status") or 0) == 2 and bool(row.get("download_url"))),
            download_url=str(row.get("download_url") or ""),
            archive_name=Path(str(
                (row.get("archive_name") if normalized else file_info.get("origin_name"))
                or f"{batch}.zip"
            )).name,
        ))
    return records


def list_s2b_batches(progress=None):
    from .batches import list_s2b_production_batches
    from .gateway import available
    if available():
        try:
            _report(progress, "正在通过共享 S2B 服务读取生产批次和人员标签…")
            return list_s2b_production_batches()
        except Exception as error:
            _report(progress, f"共享 S2B 服务暂不可用：{error}；改用本机登录继续读取")
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
    from .gateway import available, mark_downloaded, wait_for_exports
    selected = None
    if available():
        try:
            selected = wait_for_exports(pending, parse_export_rows, progress)
        except Exception as error:
            _report(progress, f"共享 S2B 下载暂不可用：{error}；改用本机登录继续下载")
    if selected is not None:
        return _download_selected(
            selected, saved, batches, output_root, progress, mark_downloaded
        )
    with _authenticated_page(progress) as page:
        from .batches import wait_for_ready_exports
        selected = wait_for_ready_exports(page, pending, progress)
        return _download_selected(
            selected, saved, batches, output_root, progress,
            lambda record_id: _api(
                page, "POST", "/factory/userExportRecord/downloadRecord", {"id": record_id}
            ),
        )


def _download_selected(selected, saved, batches, output_root, progress, mark):
    total = len(selected)
    for index, record in enumerate(selected, 1):
        archive = _download_archive(record, output_root, index, total, progress)
        saved[record.batch_number] = _extract_archive(
            archive, output_root, record.batch_number
        )
        mark(record.record_id)
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
        _sync_shared_login(self.page, self.progress)
        return self.page
    def __exit__(self, *_exc):
        self.playwright.stop()


def _records_from_page(page):
    query = ("/factory/userExportRecord?page=1&per_page=100&type=4&is_download="
             "&status=&batch_number=&created_at_before=&created_at_after=")
    return parse_export_rows(_api(page, "GET", query))


def _sync_shared_login(page, progress=None):
    from .gateway import available, refresh_login
    if not available():
        return False
    token = page.evaluate("""() => {
      const saved = localStorage.getItem('pro__Access-Token');
      if (!saved) return '';
      try { const parsed = JSON.parse(saved); return parsed.value || parsed || ''; }
      catch (_) { return saved; }
    }""")
    if not token:
        return False
    try:
        result = refresh_login(token)
    except Exception as error:
        _report(progress, f"本机 S2B 登录可用，但共享登录更新失败：{error}")
        return False
    latest = str(result.get("latest_created_at") or "").strip()
    suffix = f"，最新批次 {latest}" if latest else ""
    _report(progress, f"S2B 登录已验证并安全更新到 DTF 共享服务{suffix}。")
    return True


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


def _report(progress, message):
    if progress: progress(message)
