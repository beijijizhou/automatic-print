from pathlib import Path
from zipfile import ZipFile

from automatic_print.automation.batch_downloads import (
    download_production_images,
    extract_production_archives,
)


def test_empty_batch_plan_creates_no_downloads(tmp_path: Path) -> None:
    class EmptyPage:
        class Locator:
            pass

        def locator(self, selector):
            assert selector == "tbody tr"
            return self.Locator()

    assert download_production_images(EmptyPage(), {}, tmp_path) == []


def test_production_archive_is_extracted_into_batch_folder(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "CBT" / "123_images.zip"
    archive.parent.mkdir()
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("nested/design.png", b"image")

    folders = extract_production_archives([archive])

    assert folders == [archive.parent / "123"]
    assert (folders[0] / "nested/design.png").read_bytes() == b"image"
