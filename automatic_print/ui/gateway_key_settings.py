"""Masked local factory-gateway key entry for print settings."""

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from ..automation.api.gateway_credentials import (
    cached_client_key_available, store_local_client_key,
)


def build_gateway_key_settings(window):
    field = QLineEdit()
    field.setEchoMode(QLineEdit.Password)
    field.setClearButtonEnabled(True)
    field.setPlaceholderText("粘贴密钥；已有密钥不会回显")
    field.setToolTip("密钥只保存在当前 Windows 用户的本地凭据目录。")
    save = QPushButton("保存到本机")
    status = QLabel(_status_text())
    status.setWordWrap(True)

    def persist():
        try:
            store_local_client_key(field.text())
        except (OSError, ValueError) as error:
            status.setText(f"保存失败：{error}")
            return
        field.clear()
        status.setText("已保存到本机；后台监控会在下一次连接时自动使用。")

    save.clicked.connect(persist)
    field.returnPressed.connect(persist)
    controls = QHBoxLayout()
    controls.addWidget(field, 1)
    controls.addWidget(save)
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addLayout(controls)
    layout.addWidget(status)
    panel = QWidget(window)
    panel.setLayout(layout)
    window.gateway_key_input = field
    window.gateway_key_save_button = save
    window.gateway_key_status = status
    return panel


def _status_text():
    return (
        "本机已保存有效密钥；留空不会修改。"
        if cached_client_key_available()
        else "本机尚未保存密钥。"
    )
