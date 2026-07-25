from automatic_print.batch_ui.local_actions import image_name_rows


def test_image_names_are_listed_before_processing(tmp_path) -> None:
    nested = tmp_path / "尺码-L"
    nested.mkdir()
    (nested / "款式A-L.png").touch()
    (tmp_path / "款式B-XL.jpg").touch()
    (tmp_path / "说明.txt").touch()

    assert image_name_rows(tmp_path) == [
        ("款式A-L.png", "尺码-L/款式A-L.png"),
        ("款式B-XL.jpg", "款式B-XL.jpg"),
    ]
