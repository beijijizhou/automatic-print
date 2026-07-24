from automatic_print.crash_logging import (
    latest_log_path,
    run_with_crash_logging,
)


def test_startup_exception_is_written_to_persistent_log(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    def fail():
        raise RuntimeError("startup-test-error")

    assert run_with_crash_logging(fail) == 1
    text = latest_log_path().read_text(encoding="utf-8")
    assert "startup-test-error" in text
