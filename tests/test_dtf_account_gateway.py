import json
from io import BytesIO
from time import monotonic

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

from automatic_print.automation.api import dtf_accounts
from automatic_print.ui.dtf_accounts import DtfAccountDialog
from test_developer_mode import window


def test_dtf_status_uses_jwt_and_restricted_key_without_provider_secrets(monkeypatch):
    captured = {}
    monkeypatch.setattr(dtf_accounts, "client_key", lambda **_kwargs: "shared-key")

    def open_request(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return BytesIO(json.dumps({"platforms": [
            {"platform": "七创", "configured": True}
        ]}, ensure_ascii=False).encode())

    monkeypatch.setattr(dtf_accounts, "urlopen", open_request)
    assert dtf_accounts.account_status()[0]["platform"] == "七创"
    request = captured["request"]
    assert request.get_header("X-automatic-print-key") == "shared-key"
    assert request.get_header("Authorization").startswith("Bearer ")
    assert request.get_header("Apikey") == dtf_accounts.PUBLIC_ANON_JWT
    assert json.loads(request.data) == {"action": "status"}
    assert b"password" not in request.data
    assert captured["timeout"] == 35


def test_dtf_dialog_distinguishes_configured_and_login_verified(monkeypatch):
    monkeypatch.setattr(dtf_accounts, "account_status", lambda: [
        {"platform": "七创", "configured": True, "mode": "server_login"},
        {"platform": "Haloo", "configured": True, "mode": "browser_token"},
        {"platform": "S2B", "configured": True, "mode": "dedicated_gateway"},
    ])
    app = QApplication.instance() or QApplication([])
    dialog = DtfAccountDialog()
    deadline = monotonic() + 5
    while dialog.thread is not None and monotonic() < deadline:
        app.processEvents()
    app.processEvents()
    assert dialog.table.topLevelItemCount() == 3
    seven = dialog.table.topLevelItem(0)
    assert seven.text(2) == "未验证"
    seven.setSelected(True)
    assert dialog.verify_button.isEnabled()
    seven.setSelected(False)
    haloo = dialog.table.topLevelItem(1)
    haloo.setSelected(True)
    assert haloo.text(2) == "需网页会话验证"
    assert not dialog.verify_button.isEnabled()
    assert dialog.table.topLevelItem(2).data(0, Qt.UserRole) == "dedicated_gateway"
    dialog.reject()


def test_account_entry_is_visible_only_in_dtf_department(tmp_path):
    owner = window(tmp_path / "prefs.ini")
    button = next(button for button in owner.findChildren(QPushButton)
                  if button.text() == "DTF 平台账号")
    owner.department_selector.setCurrentIndex(
        owner.department_selector.findData("uv"))
    assert not button.isVisible()
    owner.department_selector.setCurrentIndex(
        owner.department_selector.findData("dtf"))
    assert button.isVisibleTo(owner)
    owner.department_selector.setCurrentIndex(
        owner.department_selector.findData("uv"))
    assert not button.isVisible()
    owner.close()
