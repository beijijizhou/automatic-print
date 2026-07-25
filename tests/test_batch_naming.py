from pathlib import Path

import pytest

from automatic_print.automation.batch_naming import (
    has_cvc_prefix,
    load_batch_type,
    prepare_multi_piece_names,
    save_batch_type,
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


def test_cvc_prefix_is_detected_before_layout(tmp_path: Path) -> None:
    (tmp_path / "CVC面料00004-BJRCCCQ-1.png").touch()

    assert has_cvc_prefix(tmp_path)
