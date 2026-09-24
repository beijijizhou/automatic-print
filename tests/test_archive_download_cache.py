from pathlib import Path
from zipfile import ZipFile

from automatic_print.automation.transfer.downloads import (
    download_production_images,
    extract_production_archives,
)


def test_production_archive_is_extracted_into_batch_folder(tmp_path: Path) -> None:
    archive = tmp_path / "CBT" / "123_images.zip"
    archive.parent.mkdir()
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("nested/design.png", b"image")

    folders = extract_production_archives([archive])

    assert folders == [archive.parent / "123"]
    assert (folders[0] / "nested/design.png").read_bytes() == b"image"


def test_existing_extracted_images_skip_erp_download(tmp_path: Path) -> None:
    batch_folder = tmp_path / "CBT" / "123456789012"
    batch_folder.mkdir(parents=True)
    (batch_folder / "design.png").write_bytes(b"local")
    messages = []

    class PageThatMustNotBeUsed:
        def locator(self, _selector):
            raise AssertionError("ERP should not be read for a local batch")

    saved = download_production_images(
        PageThatMustNotBeUsed(),
        {"CBT": ["123456789012"]},
        tmp_path,
        messages.append,
    )

    assert saved == [batch_folder]
    assert any("跳过下载" in message for message in messages)


def test_existing_zip_is_extracted_without_erp_download(tmp_path: Path) -> None:
    archive = tmp_path / "CBT" / "123456789012_images.zip"
    archive.parent.mkdir()
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("design.png", b"local zip")

    class PageThatMustNotBeUsed:
        def locator(self, _selector):
            raise AssertionError("ERP should not be read for a local ZIP")

    saved = download_production_images(
        PageThatMustNotBeUsed(),
        {"CBT": ["123456789012"]},
        tmp_path,
    )

    assert saved == [archive]
    assert (
        tmp_path / "CBT" / "123456789012" / "design.png"
    ).read_bytes() == b"local zip"
