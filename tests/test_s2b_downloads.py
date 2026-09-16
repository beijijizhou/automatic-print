from zipfile import ZipFile

from automatic_print.automation.api.s2b.production.downloads import (
    S2BExportRecord,
    _extract_archive,
    parse_export_rows,
)
from automatic_print.automation.api.s2b.production.batches import (
    S2BProductionBatch,
    parse_production_rows,
)


def payload(url="https://accelerate.s2bdiy.com/file.zip"):
    return {"data": {"data": [
        {"id": 9, "type": 4, "status": 2, "created_at": "2026-09-17 01:44:06",
         "export_num": 40, "export_success_num": 40, "download_url": url,
         "params": {"批次号": "22UJ9KT4VCZA"},
         "oss_file": {"origin_name": "AS2B_22UJ9KT4VCZA.zip"}},
        {"id": 8, "type": 2, "status": 2, "download_url": url,
         "params": {"批次号": "IGNORED"}},
    ]}}


def test_export_rows_keep_only_generated_production_images():
    records = parse_export_rows(payload())
    assert records == [S2BExportRecord(
        9, "22UJ9KT4VCZA", 40, "2026-09-17 01:44:06", True,
        "https://accelerate.s2bdiy.com/file.zip", "AS2B_22UJ9KT4VCZA.zip",
    )]


def test_s2b_dispatch_reuses_shared_batch_record(monkeypatch):
    record = S2BProductionBatch(
        "22UJ9KT4VCZA", 30, 40, "测试生产批次", "2026-09-17 01:44:06"
    )
    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.production.downloads.list_s2b_batches",
        lambda progress=None: [record],
    )
    from automatic_print.automation.batch_browser import load_batch_records
    result = load_batch_records("S2B")
    assert result[0].batch_number == "22UJ9KT4VCZA"
    assert result[0].piece_count == 40
    assert result[0].production_images_ready


def test_production_rows_use_progress_counts():
    records = parse_production_rows({"data": {"data": [{
        "batch_number": "22UJ9KT4VCZA",
        "name": "S2B 秋季订单",
        "created_at": "2026-09-17 01:00:00",
        "progress": {"total_num": 40, "total_print_num": 30},
    }]}})
    assert records == [S2BProductionBatch(
        "22UJ9KT4VCZA", 30, 40, "S2B 秋季订单", "2026-09-17 01:00:00"
    )]


def test_gateway_rows_include_platform_personnel_label():
    records = parse_production_rows({"records": [{
        "batch_number": "22UJ9KT4VCZA", "item_count": 30,
        "piece_count": 40, "name": "S2B 秋季订单",
        "personnel_label": "Andy", "created_at": "2026-09-17 01:00:00",
    }]})
    assert records[0].personnel_label == "Andy"


def test_gateway_export_rows_use_normalized_contract():
    records = parse_export_rows({"records": [{
        "record_id": 9, "batch_number": "22UJ9KT4VCZA",
        "image_count": 40, "created_at": "2026-09-17 01:44:06",
        "ready": True, "download_url": "https://accelerate.s2bdiy.com/file.zip",
        "archive_name": "production.zip",
    }]})
    assert records == [S2BExportRecord(
        9, "22UJ9KT4VCZA", 40, "2026-09-17 01:44:06", True,
        "https://accelerate.s2bdiy.com/file.zip", "production.zip",
    )]


def test_batch_listing_prefers_server_gateway(monkeypatch):
    from automatic_print.automation.api.s2b.production import downloads, gateway
    monkeypatch.setattr(gateway, "available", lambda: True)
    monkeypatch.setattr(gateway, "list_batches", lambda: {"records": [{
        "batch_number": "22UJ9KT4VCZA", "item_count": 30,
        "piece_count": 40, "name": "S2B 秋季订单",
        "personnel_label": "Andy", "created_at": "2026-09-17 01:00:00",
    }]})
    monkeypatch.setattr(
        downloads, "_authenticated_page",
        lambda _progress: (_ for _ in ()).throw(AssertionError("browser fallback")),
    )
    records = downloads.list_s2b_batches()
    assert records[0].personnel_label == "Andy"


def test_download_prefers_gateway_and_marks_only_after_extract(tmp_path, monkeypatch):
    from automatic_print.automation.api.s2b.production import downloads, gateway
    source = tmp_path / "source.zip"
    with ZipFile(source, "w") as bundle:
        bundle.writestr("AS2B_22UJ9KT4VCZA/S/sample.png", b"png")
    record = S2BExportRecord(
        9, "22UJ9KT4VCZA", 1, "2026-09-17 01:44:06", True,
        "https://accelerate.s2bdiy.com/file.zip", "production.zip",
    )
    events = []
    monkeypatch.setattr(gateway, "available", lambda: True)
    monkeypatch.setattr(
        gateway, "wait_for_exports",
        lambda batches, parse, progress: [record],
    )
    monkeypatch.setattr(
        gateway, "mark_downloaded", lambda record_id: events.append(("mark", record_id))
    )
    monkeypatch.setattr(
        downloads, "_download_archive", lambda *_args, **_kwargs: source
    )
    original_extract = downloads._extract_archive
    monkeypatch.setattr(
        downloads, "_extract_archive",
        lambda *args: (events.append(("extract", args[-1])), original_extract(*args))[1],
    )
    result = downloads.download_s2b_exports(
        ["22UJ9KT4VCZA"], tmp_path / "output"
    )
    assert result[0].name == "AS2B_22UJ9KT4VCZA"
    assert events == [("extract", "22UJ9KT4VCZA"), ("mark", 9)]


def test_s2b_archive_extracts_existing_root_without_extra_nesting(tmp_path):
    archive = tmp_path / "source.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("AS2B_22UJ9KT4VCZA/S/sample.png", b"png")
        bundle.writestr("AS2B_22UJ9KT4VCZA/M/sample.png", b"png")
    folder = _extract_archive(archive, tmp_path, "22UJ9KT4VCZA")
    assert folder == tmp_path / "S2B" / "BATCHES" / "AS2B_22UJ9KT4VCZA"
    assert (folder / "S" / "sample.png").read_bytes() == b"png"


def test_s2b_archive_rejects_parent_escape(tmp_path):
    import pytest
    archive = tmp_path / "unsafe.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("../outside.png", b"bad")
    with pytest.raises(RuntimeError, match="不安全路径"):
        _extract_archive(archive, tmp_path, "22UJ9KT4VCZA")
    assert not (tmp_path / "outside.png").exists()


def test_download_uses_list_url_then_marks_record_after_extract(tmp_path, monkeypatch):
    from automatic_print.automation.api.s2b.production import downloads
    source = tmp_path / "source.zip"
    with ZipFile(source, "w") as bundle:
        bundle.writestr("AS2B_22UJ9KT4VCZA/S/sample.png", b"png")

    class Page:
        calls = []
        def evaluate(self, _script, arguments):
            self.calls.append(arguments)
            return payload() if arguments["method"] == "GET" else {
                "status_code": 200, "data": [], "msg": "操作成功"
            }
    page = Page()

    class Session:
        def __enter__(self): return page
        def __exit__(self, *_args): pass

    monkeypatch.setattr(downloads, "_authenticated_page", lambda _progress: Session())
    monkeypatch.setattr(downloads, "_download_archive",
                        lambda *_args, **_kwargs: source)
    result = downloads.download_s2b_exports(
        ["22UJ9KT4VCZA"], tmp_path / "output"
    )
    assert result[0].name == "AS2B_22UJ9KT4VCZA"
    assert page.calls[-1]["path"].endswith("/downloadRecord")
    assert page.calls[-1]["payload"] == {"id": 9}


def test_missing_export_is_requested_then_polled(tmp_path, monkeypatch):
    from automatic_print.automation.api.s2b.production import downloads
    source = tmp_path / "source.zip"
    with ZipFile(source, "w") as bundle:
        bundle.writestr("AS2B_22UJ9KT4VCZA/S/sample.png", b"png")

    class Page:
        calls = []
        waits = 0
        def evaluate(self, _script, arguments):
            self.calls.append(arguments)
            if arguments["path"].startswith("/factory/userExportRecord?"):
                return {"data": {"data": []}} if not self.waits else payload()
            return {"status_code": 200, "data": [], "msg": "操作成功"}
        def wait_for_timeout(self, _milliseconds):
            self.waits += 1
    page = Page()

    class Session:
        def __enter__(self): return page
        def __exit__(self, *_args): pass

    monkeypatch.setattr(downloads, "_authenticated_page", lambda _progress: Session())
    monkeypatch.setattr(downloads, "_download_archive", lambda *_args, **_kwargs: source)
    downloads.download_s2b_exports(["22UJ9KT4VCZA"], tmp_path / "output")
    export_call = next(
        call for call in page.calls if call["path"].endswith("exportProductionImage")
    )
    assert export_call["payload"] == {"batch_number": "22UJ9KT4VCZA", "type": 1}
