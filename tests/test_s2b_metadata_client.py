import json
from io import BytesIO
from urllib.error import HTTPError

from automatic_print.automation.api.s2b.metadata.client import (
    DEFAULT_ENDPOINT,
    fetch_s2b_batch_info,
    gateway_config,
)
from automatic_print.automation.api.s2b.production.gateway import refresh_login


def test_gateway_client_posts_batch_and_account(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def read(self):
            return json.dumps({
                "records": [], "batch_number": "ABC123ABC123"
            }).encode()

    def open_request(request, timeout):
        captured["body"] = json.loads(request.data)
        captured["key"] = request.headers["X-automatic-print-key"]
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.client.urlopen", open_request
    )
    result = fetch_s2b_batch_info(
        "ABC123ABC123",
        endpoint="https://example.test/batch",
        access_key="limited-key",
    )
    assert result["batch_number"] == "ABC123ABC123"
    assert captured["body"] == {
        "account": "DTF", "batch_number": "ABC123ABC123"
    }
    assert captured["key"] == "limited-key"


def test_refresh_login_uses_restricted_gateway_action(monkeypatch):
    captured = {}

    def call(payload):
        captured.update(payload)
        return {"refreshed": True}

    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.production.gateway.call_s2b_gateway",
        call,
    )
    assert refresh_login("browser-token") == {"refreshed": True}
    assert captured == {
        "account": "DTF", "action": "refresh_login", "token": "browser-token"
    }


def test_gateway_uses_shared_endpoint_without_per_machine_url(monkeypatch):
    monkeypatch.delenv("AUTOMATIC_PRINT_S2B_BATCH_INFO_URL", raising=False)
    monkeypatch.delenv("AUTOMATIC_PRINT_S2B_BATCH_INFO_KEY", raising=False)
    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.client.shared_client_key",
        lambda: "factory-shared-key",
    )
    assert gateway_config() == (DEFAULT_ENDPOINT, "factory-shared-key")


def test_gateway_without_packaged_or_shared_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("AUTOMATIC_PRINT_S2B_BATCH_INFO_KEY", raising=False)
    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.client.shared_client_key",
        lambda: (_ for _ in ()).throw(RuntimeError("share unavailable")),
    )
    assert gateway_config() == (DEFAULT_ENDPOINT, "")


def test_gateway_posts_read_only_batch_info_without_client_key(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.client.gateway_config",
        lambda: (DEFAULT_ENDPOINT, ""),
    )

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def read(self): return b'{"records": [], "batch_number": "ABC123ABC123"}'

    def open_request(request, timeout):
        captured["headers"] = dict(request.headers)
        return Response()

    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.client.urlopen", open_request
    )
    fetch_s2b_batch_info(
        "ABC123ABC123", endpoint="https://example.test/batch", access_key=""
    )
    assert "X-automatic-print-key" not in captured["headers"]


def test_gateway_refreshes_stale_shared_key_after_401(monkeypatch):
    seen = []
    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.client.gateway_config",
        lambda: (DEFAULT_ENDPOINT, "stale-key"),
    )
    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.client.shared_client_key",
        lambda refresh_share=False: "current-key" if refresh_share else "stale-key",
    )

    def open_request(request, timeout):
        seen.append(request.get_header("X-automatic-print-key"))
        if len(seen) == 1:
            raise HTTPError(request.full_url, 401, "Unauthorized", {}, BytesIO(b"{}"))
        return BytesIO(b'{"records": [], "batch_number": "ABC123ABC123"}')

    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.client.urlopen", open_request
    )
    assert fetch_s2b_batch_info("ABC123ABC123")["records"] == []
    assert seen == ["stale-key", "current-key"]
