from pathlib import Path


def test_python_source_files_do_not_exceed_250_lines() -> None:
    root = Path(__file__).parents[1]
    oversized = []
    for folder in (root / "automatic_print", root / "tests"):
        for path in folder.rglob("*.py"):
            count = len(path.read_text(encoding="utf-8").splitlines())
            if count > 250:
                oversized.append(f"{path.relative_to(root)}: {count}")
    assert not oversized, "超过 250 行：\n" + "\n".join(oversized)
