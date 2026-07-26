from pathlib import Path

from PIL import Image

from automatic_print.resources import asset_path


def test_ha_icon_contains_windows_sizes() -> None:
    icon = asset_path("ha-icon.ico")
    assert icon.is_file()
    with Image.open(icon) as image:
        assert {(16, 16), (32, 32), (256, 256)} <= image.ico.sizes()


def test_test_computer_setup_creates_desktop_shortcut() -> None:
    root = Path(__file__).parents[1]
    script = (
        root / "windows" / "bootstrap-test-computer.ps1"
    ).read_text(encoding="utf-8")

    assert '"Haloo Automatic.lnk"' in script
    assert '"assets\\ha-icon.ico"' in script
    assert "$shortcut.Save()" in script
