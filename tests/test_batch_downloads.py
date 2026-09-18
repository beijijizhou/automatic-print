from pathlib import Path
from automatic_print.automation.transfer.downloads import (
    ExportRecordDownload,
    RemoteBatch,
    _start_parallel_downloads,
    download_production_images,
)


def test_incomplete_page_links_use_completed_export_record(tmp_path, monkeypatch):
    class Links:
        def count(self): return 2
        def nth(self, _index): return self
        def wait_for(self, **_kwargs): pass

    class Row:
        first = None
        def __init__(self): self.first = self
        def count(self): return 1
        def inner_text(self): return "生成成功 下载 下载"
        def get_by_text(self, *_args, **_kwargs): return Links()

    class Rows:
        def filter(self, **_kwargs): return Row()

    class Frame:
        def locator(self, selector):
            assert selector == "tbody tr"
            return Rows()

    from automatic_print.automation.transfer import downloads, exports
    monkeypatch.setattr(downloads, "production_batch_frame", lambda _page: Frame())
    monkeypatch.setattr(
        exports, "production_image_export_records",
        lambda *_args: {"609180613013": {
            "file_path": "https://files.hihumbird.com/batch.zip"}},
    )
    active = _start_parallel_downloads(
        object(), [RemoteBatch("BATCHES", "609180613013", tmp_path)],
        lambda _message: None,
    )

    assert len(active) == 1
    assert isinstance(active[0][1], ExportRecordDownload)


def test_empty_batch_plan_creates_no_downloads(tmp_path: Path) -> None:
    class EmptyPage:
        class Locator:
            pass

        def locator(self, selector):
            assert selector == "tbody tr"
            return self.Locator()

    assert download_production_images(EmptyPage(), {}, tmp_path) == []


def test_three_downloads_are_started_before_files_are_saved(
    tmp_path: Path,
) -> None:
    events = []

    class Download:
        pass

    class DownloadContext:
        def __init__(self, page):
            self.value = Download()
            self.page = page

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            events.append(f"started:{self.page.pending}")

    class Links:
        def __init__(self, page, number):
            self.page = page
            self.number = number
            self.waited = False

        def count(self):
            return 3

        def nth(self, index):
            assert index == 2
            self.page.pending = self.number
            return self

        def wait_for(self, state, timeout):
            assert state == "visible"
            assert timeout == 10_000
            self.waited = True
            events.append(f"waited:{self.number}")

        def click(self):
            pass

    class Row:
        def __init__(self, page, number):
            self.page = page
            self.number = number
            self.first = self

        def count(self):
            return 1

        def inner_text(self):
            return "生成成功 下载 下载 下载"

        def get_by_text(self, *_args, **_kwargs):
            return Links(self.page, self.number)

    class Rows:
        def __init__(self, page):
            self.page = page

        def filter(self, has_text):
            return Row(self.page, has_text)

        def count(self):
            return 1

    class Page:
        pending = ""

        def locator(self, selector):
            assert selector in {"tbody tr", "tbody tr, th"}
            return Rows(self)

        def expect_download(self, timeout):
            assert timeout == 120_000
            return DownloadContext(self)

    tasks = [
        RemoteBatch("批次", f"12345678901{i}", tmp_path)
        for i in range(3)
    ]
    active = _start_parallel_downloads(Page(), tasks, None)

    assert len(active) == 3
    assert events == [
        "waited:123456789010",
        "started:123456789010",
        "waited:123456789011",
        "started:123456789011",
        "waited:123456789012",
        "started:123456789012",
    ]


def test_download_uses_batch_archive_name_and_removes_browser_copy(
    tmp_path: Path, monkeypatch,
) -> None:
    events = []

    class Download:
        suggested_filename = "57f07883-7ea5-4e0d-991d-7163f3a00473"

        def save_as(self, destination):
            Path(destination).write_bytes(b"downloaded archive")
            events.append(("saved", Path(destination).name))

        def delete(self):
            events.append(("deleted", self.suggested_filename))

    class DownloadContext:
        value = Download()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

    class Links:
        def count(self):
            return 3

        def nth(self, _index):
            return self

        def wait_for(self, **_kwargs):
            pass

        def click(self):
            pass

    class Row:
        first = None

        def __init__(self):
            self.first = self

        def count(self):
            return 1

        def inner_text(self):
            return "生成成功 下载 下载 下载"

        def get_by_text(self, *_args, **_kwargs):
            return Links()

    class Rows:
        def filter(self, **_kwargs):
            return Row()

    class Frame:
        def locator(self, selector):
            if selector == "tbody tr":
                return Rows()
            raise AssertionError(selector)

    class Page:
        def expect_download(self, **_kwargs):
            return DownloadContext()

    from automatic_print.automation.transfer import downloads
    monkeypatch.setattr(downloads, "production_batch_frame", lambda _page: Frame())
    monkeypatch.setattr(downloads, "_search_batches", lambda *_args: None)
    destination_root = tmp_path / "隆丰"
    saved = download_production_images(
        Page(), {"BATCHES": ["609162027027"]}, destination_root,
        extract=False,
    )

    expected = destination_root / "BATCHES" / "609162027027_生产图.zip"
    assert saved == [expected]
    assert expected.read_bytes() == b"downloaded archive"
    assert events == [
        ("saved", "609162027027_生产图.zip"),
        ("deleted", "57f07883-7ea5-4e0d-991d-7163f3a00473"),
    ]
