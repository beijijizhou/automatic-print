from time import monotonic

from PySide6.QtWidgets import QApplication

from automatic_print.automation.api.s2b.metadata.store import register_batch_records
from automatic_print.runtime.cancellation import Cancellation
from automatic_print.ui.batch_folder_colors import read_folder_colors
from automatic_print.ui.batch_folder_selection import BatchFolderSelectionDialog


def _batch(tmp_path):
    root = tmp_path / "AS2B014Mt______2_NIL7IEHTIK3E_20260921_012330_be8dix9e"
    black = root / "S" / "NIL7IEHTIK3E-1-1-ORDER7-1-1-1-1-棉-S.png"
    white = root / "M" / "NIL7IEHTIK3E-1-1-ORDER8-1-1-1-1-棉-M.png"
    for image in (black, white):
        image.parent.mkdir(parents=True)
        image.touch()
    return root, black, white


def test_s2b_folder_colors_are_local_to_each_size_folder(tmp_path, monkeypatch):
    root, black, white = _batch(tmp_path)
    calls = []

    def prepare(paths, _settings, _progress):
        calls.append(list(paths))
        register_batch_records(paths, {
            "batch_number": "NIL7IEHTIK3E",
            "records": [
                {"order_code": "ORDER7", "order_item_code": "ORDER7-1",
                 "color": "黑色", "size": "S"},
                {"order_code": "ORDER8", "order_item_code": "ORDER8-1",
                 "color": "白色", "size": "M"},
            ],
        })
        return [{"batch_number": "NIL7IEHTIK3E", "warning": ""}]

    monkeypatch.setattr(
        "automatic_print.ui.batch_folder_colors.prepare_s2b_metadata", prepare)
    result = read_folder_colors([
        {"folder": root / "S", "images": [black]},
        {"folder": root / "M", "images": [white]},
    ], Cancellation())
    assert len(calls) == 1
    assert result[str(root / "S")] == ("黑色1张", "")
    assert result[str(root / "M")] == ("白色1张", "")


def test_folder_picker_displays_colors_after_background_scan(tmp_path, monkeypatch):
    root, _, _ = _batch(tmp_path)
    monkeypatch.setattr(
        "automatic_print.ui.batch_folder_colors.read_folder_colors",
        lambda batches, cancellation, progress: {
            str(root / "S"): ("黑色1张", ""),
            str(root / "M"): ("白色1张", ""),
        },
    )
    app = QApplication.instance() or QApplication([])
    dialog = BatchFolderSelectionDialog(None, root)
    deadline = monotonic() + 5
    while dialog.thread.isRunning() and monotonic() < deadline:
        app.processEvents()
    app.processEvents()
    assert dialog.folders.headerItem().text(2) == "颜色"
    colors = {
        dialog.folders.topLevelItem(index).text(2)
        for index in range(dialog.folders.topLevelItemCount())
    }
    assert colors == {"黑色1张", "白色1张"}
    dialog.reject()
