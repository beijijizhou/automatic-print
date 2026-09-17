import json

from automatic_print.automation.api.s2b.metadata.client import (
    DEFAULT_ENDPOINT,
    fetch_s2b_batch_info,
    gateway_config,
)


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


def test_gateway_uses_shared_endpoint_without_per_machine_url(monkeypatch):
    monkeypatch.delenv("AUTOMATIC_PRINT_S2B_BATCH_INFO_URL", raising=False)
    monkeypatch.delenv("AUTOMATIC_PRINT_S2B_BATCH_INFO_KEY", raising=False)
    assert gateway_config() == (DEFAULT_ENDPOINT, "")


def test_gateway_posts_read_only_batch_info_without_client_key(monkeypatch):
    captured = {}

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
