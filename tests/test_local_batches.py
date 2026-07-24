from pathlib import Path

from automatic_print.automation.local_batches import discover_local_batches


def test_discovers_downloaded_batches_but_not_processed_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "Haloo" / "BATCHES" / "123456789012"
    source.mkdir(parents=True)
    (source / "design.png").write_bytes(b"image")
    processed = tmp_path / "Haloo" / "PROCESSED" / "123456789012"
    processed.mkdir(parents=True)
    (processed / "print.png").write_bytes(b"output")

    records = discover_local_batches(tmp_path, "Haloo")

    assert len(records) == 1
    assert records[0].batch_number == "123456789012"
    assert records[0].image_count == 1
    assert records[0].folder == source


def test_local_batches_are_scoped_to_platform(tmp_path: Path) -> None:
    folder = tmp_path / "隆丰" / "BATCHES" / "123456789012"
    folder.mkdir(parents=True)
    (folder / "design.jpg").write_bytes(b"image")

    assert discover_local_batches(tmp_path, "Haloo") == []
