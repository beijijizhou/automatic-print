import json

import pytest

from scripts.sync_dtf_platform_credentials import (
    collect_profiles, synchronize,
)


def _private_tree(tmp_path):
    private = tmp_path / ".streamlit"
    private.mkdir()
    local = [
        f'[factory_credentials."{name}"]\n' +
        "\n".join(f'{field} = "sample-{field}"' for field in fields)
        for name, fields in {
            "Haloo": ("token",), "隆丰": ("token",), "莆田": ("token",),
            "一朵云": ("username", "password"),
            "七创": ("username", "password"),
            "汉森": ("username", "password", "client_id"),
            "方果": ("username", "password", "tenant_id"),
        }.items()
    ]
    (private / "local_factory_credentials.toml").write_text(
        "\n\n".join(local), encoding="utf-8")
    sds = [
        f'[factory_credentials."{name}"]\n' +
        "\n".join(f'{field} = "sample-{field}"' for field in
                  ("contact_tel", "extraInfo", "factory_code", "password"))
        for name in ("1号线", "2号线")
    ]
    (private / "secrets.toml").write_text("\n\n".join(sds), encoding="utf-8")
    return private


def test_sync_collects_only_active_dtf_profiles(tmp_path):
    _private_tree(tmp_path)
    profiles = collect_profiles(tmp_path)
    assert len(profiles) == 9
    assert "一朵云" in profiles and "七创" in profiles
    assert "赛博" not in profiles and "S2B" not in profiles


def test_missing_credential_prevents_any_remote_write(tmp_path, monkeypatch):
    private = _private_tree(tmp_path)
    path = private / "local_factory_credentials.toml"
    path.write_text(path.read_text(encoding="utf-8").replace(
        'password = "sample-password"', 'password = ""', 1), encoding="utf-8")
    monkeypatch.setattr(
        "scripts.sync_dtf_platform_credentials.subprocess.run",
        lambda *_args, **_kwargs: pytest.fail("must not upload partial profiles"),
    )
    with pytest.raises(ValueError, match="未覆盖服务端配置"):
        collect_profiles(tmp_path)


def test_sync_uploads_one_server_secret_without_logging_values(monkeypatch):
    captured = {}

    def run(command, **kwargs):
        captured["command"] = command
        assert kwargs["capture_output"] is True
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr("scripts.sync_dtf_platform_credentials.subprocess.run", run)
    synchronize({"七创": {"username": "sample", "password": "test-only"}}, "project")
    payload = captured["command"][5]
    assert json.loads(payload.split("=", 1)[1])["七创"]["username"] == "sample"
    assert "--project-ref" in captured["command"]
