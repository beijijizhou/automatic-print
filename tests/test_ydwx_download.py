import json
from io import BytesIO
from urllib.error import HTTPError
from zipfile import ZipFile

import pytest

from automatic_print.automation.api.ydwx import YdwxBatch, parse_batches
from automatic_print.automation.api.ydwx import batches, credentials, downloads, gateway


def batch(task_id=11, name="K_YX_05_Tie_2030__322", count=2, downloaded=2):
    return YdwxBatch(task_id, "20260921011", name, "2026-09-21", count, downloaded, 2)


def archive_bytes():
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("one.png", b"image")
    return stream.getvalue()


def test_batch_list_uses_shared_gateway_without_platform_token(monkeypatch):
    requests = []
    payload = {"dateList": [{"date": "2026-09-21", "producingTaskList": [{
        "id": 11, "no": "20260921011", "name": "UV_2030",
        "manuscriptNum": 1,
    }]}]}

    def open_gateway(body, timeout):
        requests.append((body, timeout))
        return BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(batches, "request_gateway", open_gateway)
    assert batches.list_batches()[0].name == "UV_2030"
    assert requests == [({"action": "list"}, 30)]


def test_gateway_reuses_packaged_client_key_without_sds_credentials(monkeypatch):
    seen = []
    monkeypatch.setattr(gateway, "client_key", lambda **_kwargs: "restricted-key")

    def open_request(request, timeout):
        seen.append((request, timeout))
        return BytesIO(b"{}")

    monkeypatch.setattr(gateway, "urlopen", open_request)
    with gateway.request_gateway({"action": "list"}, timeout=10):
        pass
    request, timeout = seen[0]
    assert timeout == 10
    assert request.get_header("X-automatic-print-key") == "restricted-key"
    assert b"contact_tel" not in request.data
    assert b"password" not in request.data


def test_source_gateway_key_is_read_once_from_share_then_cached(tmp_path, monkeypatch):
    shared = tmp_path / "share" / "ydwx-gateway.key"
    shared.parent.mkdir()
    shared.write_text("s" * 48, encoding="utf-8")
    cached = tmp_path / "profile" / "AutomaticPrint" / "credentials" / "ydwx-gateway.key"
    monkeypatch.setenv("AUTOMATIC_PRINT_YDWX_SHARE_KEY_FILE", str(shared))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    monkeypatch.delenv("AUTOMATIC_PRINT_YDWX_KEY", raising=False)
    monkeypatch.delenv("AUTOMATIC_PRINT_S2B_BATCH_INFO_KEY", raising=False)
    monkeypatch.setattr(credentials, "gateway_client_key", lambda: "")
    assert credentials.client_key() == "s" * 48
    assert cached.read_text(encoding="utf-8") == "s" * 48
    shared.unlink()
    assert credentials.client_key() == "s" * 48


def test_source_gateway_reports_missing_share_without_login(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOMATIC_PRINT_YDWX_SHARE_KEY_FILE", str(tmp_path / "missing.key"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    monkeypatch.delenv("AUTOMATIC_PRINT_YDWX_KEY", raising=False)
    monkeypatch.setattr(credentials, "gateway_client_key", lambda: "")
    with pytest.raises(RuntimeError, match="本机缓存尚未建立"):
        credentials.client_key()


def test_gateway_retries_stale_cache_with_current_share_key(monkeypatch):
    seen = []
    monkeypatch.setattr(gateway, "client_key", lambda refresh_share=False: (
        "new-shared-key" if refresh_share else "stale-cached-key"
    ))

    def open_request(request, timeout):
        seen.append(request.get_header("X-automatic-print-key"))
        if len(seen) == 1:
            raise HTTPError(request.full_url, 401, "Unauthorized", {}, BytesIO(b'{}'))
        return BytesIO(b'{}')

    monkeypatch.setattr(gateway, "urlopen", open_request)
    with gateway.request_gateway({"action": "list"}):
        pass
    assert seen == ["stale-cached-key", "new-shared-key"]


def test_parse_dated_batches_keeps_name_number_and_counts():
    records = parse_batches({"dateList": [
        {"date": "2026-09-20", "producingTaskList": [{
            "id": 10, "no": "20260920001", "name": "old",
            "manuscriptNum": 2, "downNum": 1, "totalProductNum": 3,
        }]},
        {"date": "2026-09-21", "producingTaskList": [{
            "id": 11, "no": "20260921011", "name": "K_YX_05_Tie_2030__322",
            "manuscriptNum": 322, "downNum": 322, "totalProductNum": 322,
        }]},
    ]})
    assert [record.name for record in records] == ["K_YX_05_Tie_2030__322", "old"]
    assert records[0].number == "20260921011"
    assert records[0].manuscript_count == 322


def test_download_uses_verified_batch_name_and_redown_mode(tmp_path, monkeypatch):
    source = batch()
    monkeypatch.setattr(downloads, "list_batches", lambda: [source])
    requests = []

    class Response(BytesIO):
        pass

    def open_request(payload):
        requests.append(payload)
        return Response(archive_bytes())

    monkeypatch.setattr(downloads, "request_gateway", open_request)
    saved, failures = downloads.download_batches([source], tmp_path)
    assert not failures
    assert len(saved) == 1
    assert saved[0][1].name == "完整稿件.zip"
    assert source.name in str(saved[0][1])
    assert requests == [{"action": "download", "task_id": 11, "mode": "redown"}]
    assert saved[0][1].is_file()


def test_changed_batch_is_skipped_without_blocking_next(tmp_path, monkeypatch):
    first = batch(11, "old")
    second = batch(12, "current")
    monkeypatch.setattr(downloads, "list_batches", lambda: [batch(11, "changed"), second])
    monkeypatch.setattr(downloads, "request_gateway", lambda *_a, **_k: BytesIO(archive_bytes()))
    saved, failures = downloads.download_batches([first, second], tmp_path)
    assert [record.name for record, _path in saved] == ["current"]
    assert failures[0][0] == "old"


def test_invalid_zip_is_retained_as_incomplete_not_published(tmp_path, monkeypatch):
    monkeypatch.setattr(downloads, "request_gateway", lambda *_a, **_k: BytesIO(b"not a zip"))
    with pytest.raises(ValueError, match="ZIP 校验"):
        downloads.download_batch(batch(), tmp_path)
    assert not list(tmp_path.rglob("*.zip"))
    assert len(list(tmp_path.rglob("*.未完成"))) == 1


def test_existing_zip_is_reused_only_for_same_batch_snapshot(tmp_path, monkeypatch):
    source = batch()
    monkeypatch.setattr(downloads, "request_gateway", lambda *_a, **_k: BytesIO(archive_bytes()))
    archive = downloads.download_batch(source, tmp_path)
    monkeypatch.setattr(downloads, "request_gateway", lambda *_a, **_k: (
        (_ for _ in ()).throw(AssertionError("must not download again"))
    ))
    assert downloads.download_batch(source, tmp_path) == archive
    with pytest.raises(FileExistsError, match="稿件数或状态已变化"):
        downloads.download_batch(batch(count=3, downloaded=3), tmp_path)
    assert archive.is_file()


def test_platform_600_item_limit_skips_only_oversized_batch(tmp_path, monkeypatch):
    oversized = batch(11, "oversized", 601, 601)
    small = batch(12, "small")
    monkeypatch.setattr(downloads, "list_batches", lambda: [oversized, small])
    monkeypatch.setattr(downloads, "request_gateway", lambda *_a, **_k: BytesIO(archive_bytes()))
    saved, failures = downloads.download_batches([oversized, small], tmp_path)
    assert [record.name for record, _path in saved] == ["small"]
    assert failures[0][0] == "oversized"
    assert "600" in failures[0][1]


def test_uv_download_page_lists_ydwx_without_dtf_layout_controls(tmp_path):
    from test_developer_mode import window

    owner = window(tmp_path / "ydwx.ini", department=None)
    page = owner.production_platform_download_page
    assert page.platform_checks["亿点万象"].isChecked()
    ydwx = page.workbenches["亿点万象"]
    assert not hasattr(ydwx, "token")
    assert ydwx.download.isEnabled() is False
    ydwx._finished(("list", [batch()]))
    assert ydwx.table.item(0, 2).text() == "K_YX_05_Tie_2030__322"
    assert ydwx.table.item(0, 4).text() == "2/2"
    assert ydwx.table.item(0, 6).text() == "2030铁"
    assert "48 张" in ydwx.table.item(0, 7).text()
    owner.department_selector.setCurrentIndex(owner.department_selector.findData("dtf"))
    assert not page.platform_checks["亿点万象"].isChecked()
    owner.close()
