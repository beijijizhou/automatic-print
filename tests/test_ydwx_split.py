import json
from zipfile import ZipFile

import pytest

from automatic_print.automation.api.ydwx import downloads
from automatic_print.automation.api.ydwx.archive_split import split_uv_archive
from automatic_print.layout_engine.uv import identify_uv_batch_material, uv_sheet_capacity


@pytest.mark.parametrize("name,expected,capacity", [
    ("QW_YX_10_Tie_2030__504", "2030_iron", 48),
    ("E_YX_03_Tie_1040__365", "1040", 72),
    ("A_YX_09_Tie_yuan_2020__183", "round_iron", 72),
    ("A_YX_09_Lv_yuan_2020__183", "raw_aluminum", 72),
    ("E_YX_03_Lv_2030__12", "2030_aluminum", 48),
    ("E_YX_03_Muban_2030__12", "2030_wood", 48),
    ("E_YX_03_Tie_3040__12", "3040", 24),
    ("E_YX_03_Guazhong_2525__12", "clock_2525", 45),
    ("E_YX_03_CHEPAI__12", "license_plate", 64),
])
def test_uv_sku_matches_catalog_and_canvas_capacity(name, expected, capacity):
    spec = identify_uv_batch_material(name)
    assert spec.key == expected
    assert uv_sheet_capacity(spec) == capacity


def test_ambiguous_or_unrelated_batch_is_not_assigned_a_material():
    assert identify_uv_batch_material("YX_DTF_2030__504") is None
    assert identify_uv_batch_material("YX_unknown__1040") is None
    assert identify_uv_batch_material("YX_Tie_2030_Lv_2030__12") is None


def write_archive(path, count, *, duplicate_names=False):
    with ZipFile(path, "w") as bundle:
        for index in range(count):
            name = (f"order-{index}/image.png" if duplicate_names else
                    f"order-{index:04d}.png")
            bundle.writestr(name, f"image {index}".encode())
        bundle.writestr("notes.txt", "keep in ZIP")


def test_504_images_become_ten_full_2030_folders_and_one_partial(tmp_path):
    archive = tmp_path / "完整稿件.zip"
    write_archive(archive, 504, duplicate_names=True)
    spec = identify_uv_batch_material("QW_YX_10_Tie_2030__504")

    result = split_uv_archive(archive, spec, expected_count=252)

    assert result.image_count == 504
    assert result.capacity == 48
    assert [folder.name for folder in result.folders] == (
        [f"{index}-48" for index in range(1, 11)] + ["11-24"]
    )
    assert [len(list(folder.glob("*.png"))) for folder in result.folders] == [48] * 10 + [24]
    assert archive.is_file()
    assert "接口稿件数 252" in result.warning
    manifest = json.loads((result.root / "分组信息.json").read_text(encoding="utf-8"))
    assert len({item["path"] for item in manifest["files"]}) == 504
    assert manifest["files"][0]["source"] == "order-0/image.png"
    assert split_uv_archive(archive, spec).folders == result.folders


def test_49_images_make_48_plus_one_without_renaming_source_zip(tmp_path):
    archive = tmp_path / "新增稿件.zip"
    write_archive(archive, 49)
    spec = identify_uv_batch_material("E_YX_03_Tie_2030__49")
    result = split_uv_archive(archive, spec)
    assert [folder.name for folder in result.folders] == ["1-48", "2-1"]
    assert result.root.name == "新增稿件-分组"
    assert archive.is_file()


def test_1040_groups_seventy_two_images_per_canvas(tmp_path):
    archive = tmp_path / "完整稿件.zip"
    write_archive(archive, 73)
    spec = identify_uv_batch_material("NJ_YX_17_Tie_1040__73")
    result = split_uv_archive(archive, spec)
    assert result.capacity == 72
    assert [folder.name for folder in result.folders] == ["1-72", "2-1"]
    assert [len(list(folder.glob("*.png"))) for folder in result.folders] == [72, 1]


def test_known_order_is_not_cut_at_canvas_boundary(tmp_path):
    archive = tmp_path / "完整稿件.zip"
    with ZipFile(archive, "w") as bundle:
        for index in range(47):
            bundle.writestr(f"single-{index:03d}.png", b"image")
        bundle.writestr("2010200000303683_front.png", b"front")
        bundle.writestr("2010200000303683_back.png", b"back")
    spec = identify_uv_batch_material("E_YX_03_Tie_2030__49")
    result = split_uv_archive(archive, spec)
    assert [folder.name for folder in result.folders] == ["1-47", "2-2"]
    assert len(list(result.folders[1].glob("*.png"))) == 2


def test_one_order_larger_than_canvas_keeps_zip_unpublished(tmp_path):
    archive = tmp_path / "完整稿件.zip"
    with ZipFile(archive, "w") as bundle:
        for index in range(49):
            bundle.writestr(f"2010200000303683_{index}.png", b"image")
    spec = identify_uv_batch_material("E_YX_03_Tie_2030__49")
    with pytest.raises(ValueError, match="超过单画布 48 张"):
        split_uv_archive(archive, spec)
    assert archive.exists()
    assert not (tmp_path / "完整稿件-分组").exists()


def test_existing_split_with_missing_file_is_preserved_and_reported(tmp_path):
    archive = tmp_path / "完整稿件.zip"
    write_archive(archive, 1)
    spec = identify_uv_batch_material("E_YX_03_Tie_2030__1")
    result = split_uv_archive(archive, spec)
    next(result.folders[0].iterdir()).unlink()
    with pytest.raises(ValueError, match="已有分组.*未通过复核"):
        split_uv_archive(archive, spec)
    assert result.root.exists()
    assert archive.exists()


def test_unsafe_zip_member_never_publishes_split(tmp_path):
    archive = tmp_path / "完整稿件.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("../escape.png", b"bad")
    spec = identify_uv_batch_material("E_YX_03_Tie_2030__1")
    with pytest.raises(ValueError, match="不安全路径"):
        split_uv_archive(archive, spec)
    assert archive.exists()
    assert not (tmp_path / "完整稿件-分组").exists()


def test_unrecognized_download_keeps_original_zip_and_reports_pending(tmp_path, monkeypatch):
    source = downloads.YdwxBatch(11, "20260921011", "DTF_unknown_2030", "2026-09-21", 1, 1, 1)
    monkeypatch.setattr(downloads, "list_batches", lambda: [source])
    monkeypatch.setattr(downloads, "request_gateway", lambda *_a, **_k: _response())
    saved, failures = downloads.download_batches([source], tmp_path)
    assert len(saved) == 1 and saved[0][1].exists()
    assert failures[0][0] == source.name
    assert "未猜测尺寸" in failures[0][1]


def _response():
    from io import BytesIO
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("image.png", b"image")
    stream.seek(0)
    return stream
