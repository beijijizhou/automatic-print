from PySide6.QtWidgets import QLineEdit, QWidget

from automatic_print.ui import gateway_key_settings
from test_developer_mode import APP


def test_gateway_key_entry_is_masked_and_saves_without_echo(monkeypatch):
    saved = []
    monkeypatch.setattr(gateway_key_settings, "cached_client_key_available", lambda: False)
    monkeypatch.setattr(gateway_key_settings, "store_local_client_key", saved.append)
    owner = QWidget()
    panel = gateway_key_settings.build_gateway_key_settings(owner)
    assert panel.isAncestorOf(owner.gateway_key_input)
    assert owner.gateway_key_input.echoMode() == QLineEdit.Password
    assert "尚未保存" in owner.gateway_key_status.text()
    owner.gateway_key_input.setText("m" * 64)
    owner.gateway_key_save_button.click()
    APP.processEvents()
    assert saved == ["m" * 64]
    assert owner.gateway_key_input.text() == ""
    assert "已保存到本机" in owner.gateway_key_status.text()
