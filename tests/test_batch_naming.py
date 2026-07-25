from pathlib import Path

import pytest

from automatic_print.automation.batch_naming import (
    has_source_prefix,
    load_batch_type,
    prepare_multi_piece_names,
    save_batch_type,
    sort_multi_piece_images,
)


def test_multi_piece_batch_removes_cvc_prefix(tmp_path: Path) -> None:
    original = tmp_path / "CVC面料00004-BJRCCCQ-1-1000M--_437-白色-XL-NO1-1.png"
    original.touch()

    assert prepare_multi_piece_names(tmp_path, "多项多件") == 1
    assert not original.exists()
    assert (
        tmp_path / "BJRCCCQ-1-1000M--_437-白色-XL-NO1-1.png"
    ).exists()


def test_single_piece_batch_keeps_original_name(tmp_path: Path) -> None:
    original = tmp_path / "CVC面料00004-BJRCCCQ-1-白色-XL.png"
    original.touch()

    assert prepare_multi_piece_names(tmp_path, "单项单件") == 0
    assert original.exists()


def test_rename_collision_stops_without_overwriting(tmp_path: Path) -> None:
    original = tmp_path / "CVC面料00004-BJRCCCQ-1.png"
    existing = tmp_path / "BJRCCCQ-1.png"
    original.write_bytes(b"original")
    existing.write_bytes(b"existing")

    with pytest.raises(RuntimeError, match="覆盖已有文件"):
        prepare_multi_piece_names(tmp_path, "单项多件")

    assert original.read_bytes() == b"original"
    assert existing.read_bytes() == b"existing"


def test_batch_type_metadata_round_trip(tmp_path: Path) -> None:
    save_batch_type(tmp_path, "单项多件")

    assert load_batch_type(tmp_path) == "单项多件"


def test_source_prefix_is_detected_before_layout(tmp_path: Path) -> None:
    (tmp_path / "CVC面料00004-BJRCCCQ-1.png").touch()

    assert has_source_prefix(tmp_path)


def test_longfeng_prefix_is_removed_once(tmp_path: Path) -> None:
    original = tmp_path / "A0000007-BJRCCCQ-1-白色-XL-NO1-1.png"
    original.touch()

    assert prepare_multi_piece_names(tmp_path, "多项多件") == 1
    renamed = tmp_path / "BJRCCCQ-1-白色-XL-NO1-1.png"
    assert renamed.exists()
    assert prepare_multi_piece_names(tmp_path, "多项多件") == 0
    assert renamed.exists()


def test_future_platform_removes_first_segment_once(tmp_path: Path) -> None:
    save_batch_type(tmp_path, "单项多件")
    original = tmp_path / "未来平台款号99-BJRCCCQ-1-白色-XL.png"
    original.touch()

    assert prepare_multi_piece_names(tmp_path, "单项多件") == 1
    renamed = tmp_path / "BJRCCCQ-1-白色-XL.png"
    assert renamed.exists()
    assert prepare_multi_piece_names(tmp_path, "单项多件") == 0
    assert renamed.exists()


def test_legacy_normalized_batch_is_not_renamed_again(
    tmp_path: Path,
) -> None:
    metadata = tmp_path / ".automatic-print-batch.json"
    metadata.write_text('{"batch_type": "多项多件"}', encoding="utf-8")
    normalized = tmp_path / "BJRCCCQ-1-白色-XL.png"
    normalized.touch()

    save_batch_type(tmp_path, "多项多件")

    assert prepare_multi_piece_names(tmp_path, "多项多件") == 0
    assert normalized.exists()


def test_same_order_and_color_sorts_sizes_small_to_large() -> None:
    names = [
        "B8S9E55-1-T-LSJ-Black-4Xl-NO1-1.png",
        "B8S9E55-1-T-LSJ-White-M-NO1-1.png",
        "B8S9E55-1-T-LSJ-Black-XL-NO1-1.png",
        "B8S9E55-1-T-LSJ-Black-S-NO1-1.png",
        "B8S9E55-1-T-LSJ-Black-2XL-NO1-1.png",
    ]

    ordered = sort_multi_piece_images([Path(name) for name in names])

    assert [path.name for path in ordered] == [
        "B8S9E55-1-T-LSJ-Black-S-NO1-1.png",
        "B8S9E55-1-T-LSJ-Black-XL-NO1-1.png",
        "B8S9E55-1-T-LSJ-Black-2XL-NO1-1.png",
        "B8S9E55-1-T-LSJ-Black-4Xl-NO1-1.png",
        "B8S9E55-1-T-LSJ-White-M-NO1-1.png",
    ]


def test_repeated_x_sizes_are_sorted_naturally() -> None:
    names = [
        Path("ORDER-Black-XXXL-NO1-1.png"),
        Path("ORDER-Black-L-NO1-1.png"),
        Path("ORDER-Black-XXL-NO1-1.png"),
    ]

    assert [path.name for path in sort_multi_piece_images(names)] == [
        "ORDER-Black-L-NO1-1.png",
        "ORDER-Black-XXL-NO1-1.png",
        "ORDER-Black-XXXL-NO1-1.png",
    ]
