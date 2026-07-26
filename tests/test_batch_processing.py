from automatic_print.batch_ui.processing import process_local_batches
from automatic_print.layout import LayoutSettings


def test_selected_batches_are_merged_in_selection_order(
    tmp_path, monkeypatch
) -> None:
    first = tmp_path / "Haloo" / "BATCHES" / "607250203001"
    second = tmp_path / "Haloo" / "BATCHES" / "607250203002"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "ORDER-A-Black-S-NO1-1.png").touch()
    (second / "ORDER-B-White-M-NO1-1.png").touch()
    captured = {}

    def generate(images, destination, _settings, progress):
        captured["names"] = [image.name for image in images]
        captured["destination"] = destination
        progress("合成图片", len(images), len(images), images[-1].name)
        return {"file": "print.png"}

    monkeypatch.setattr(
        "automatic_print.batch_ui.processing.generate_layout", generate
    )
    messages = []

    result = process_local_batches(
        tmp_path,
        "Haloo",
        ["607250203002", "607250203001"],
        {},
        LayoutSettings(),
        None,
        True,
        messages.append,
    )

    assert captured["names"] == [
        "ORDER-B-White-M-NO1-1.png",
        "ORDER-A-Black-S-NO1-1.png",
    ]
    assert captured["destination"].name.startswith("MERGED_")
    assert result["merged_batches"] == ["607250203002", "607250203001"]
    assert any("正在合并 2 个批次" in message for message in messages)
