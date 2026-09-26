from unittest.mock import Mock

from automatic_print.automation.browser import chrome


def test_existing_playwright_chrome_is_reused(monkeypatch):
    launch = Mock()
    messages = []
    monkeypatch.setattr(chrome, "chrome_is_connectable", lambda: True)
    monkeypatch.setattr(chrome.subprocess, "Popen", launch)

    chrome.ensure_debug_chrome("https://example.test", progress=messages.append)

    launch.assert_not_called()
    assert any("复用现有浏览器" in message for message in messages)


def test_concurrent_start_waits_for_first_browser(tmp_path, monkeypatch):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / chrome.STARTUP_LOCK).touch()
    states = iter((False, True))
    launch = Mock()
    messages = []
    monkeypatch.setattr(chrome, "_profile_dir", lambda: profile)
    monkeypatch.setattr(chrome, "chrome_is_connectable", lambda: next(states))
    monkeypatch.setattr(chrome.subprocess, "Popen", launch)

    chrome.ensure_debug_chrome("https://example.test", progress=messages.append)

    launch.assert_not_called()
    assert any("复用现有浏览器" in message for message in messages)
