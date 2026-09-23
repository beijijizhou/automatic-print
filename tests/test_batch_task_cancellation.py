from unittest.mock import MagicMock, patch

import pytest

from automatic_print.automation.browser.session import open_authenticated_page
from automatic_print.batch_ui.task.actions import ThreadActionsMixin
from automatic_print.batch_ui.task.worker import AutomationWorker
from automatic_print.runtime.cancellation import TaskCancelled


class _TextWidget:
    def __init__(self):
        self.text = ""
        self.enabled = True

    def setText(self, text):
        self.text = text

    def setEnabled(self, enabled):
        self.enabled = enabled


class _Log:
    def __init__(self):
        self.lines = []

    def appendPlainText(self, text):
        self.lines.append(text)


class _TaskUi(ThreadActionsMixin):
    def __init__(self, worker):
        self.worker = worker
        self.stop_button = _TextWidget()
        self.loading_label = _TextWidget()
        self.loading_bar = MagicMock()
        self.log = _Log()


def test_stop_batch_reading_uses_matching_status_without_riin():
    worker = AutomationWorker("list", "隆丰")
    ui = _TaskUi(worker)

    ui.stop_current_task()

    assert worker.cancellation.requested()
    assert ui.loading_label.text == "步骤 1 · 正在停止批次信息读取…"
    assert ui.log.lines == ["正在停止批次信息读取…"]
    assert "RIIN" not in ui.loading_label.text
    assert not ui.stop_button.enabled

    ui.task_cancelled()
    assert ui.loading_label.text == "批次信息读取已停止。"


def test_current_automation_step_shows_step_and_elapsed_time():
    ui = _TaskUi(AutomationWorker("list", "隆丰"))
    ui._task_started_at = 90

    with patch(
        "automatic_print.batch_ui.task.actions.monotonic",
        side_effect=(100, 106),
    ):
        ui.show_progress_message("正在等待生产批次表格加载…")

    assert ui.loading_label.text == (
        "步骤 1 · 正在等待生产批次表格加载…"
        "（本步骤 6 秒 · 总计 16 秒）"
    )


def test_automation_log_keeps_layout_and_riin_steps():
    ui = _TaskUi(AutomationWorker("download", "隆丰", auto_print=True))

    ui.append_log("正在保存大图 · 已写入 20.0 兆字节")
    ui.append_log("RIIN正在生成PRN")

    assert ui.log.lines == [
        "正在保存大图 · 已写入 20.0 兆字节",
        "RIIN正在生成PRN",
    ]


def test_riin_stop_status_is_limited_to_automatic_print():
    regular = AutomationWorker("download", "隆丰")
    automatic = AutomationWorker("download", "隆丰", auto_print=True)

    assert "RIIN" not in regular.stop_pending_text
    assert "RIIN" in automatic.stop_pending_text


def test_authenticated_page_wait_honours_cancellation():
    target = "https://longfeng.merchant.hihumbird.com/factory/items"
    page = MagicMock()
    page.url = target
    page.locator.return_value.first.count.return_value = 0
    browser = MagicMock()
    browser.contexts = [MagicMock(pages=[page])]
    checks = 0

    def cancel_after_first_wait():
        nonlocal checks
        checks += 1
        if checks >= 3:
            raise TaskCancelled()

    with pytest.raises(TaskCancelled):
        open_authenticated_page(
            browser,
            target,
            ".search-container",
            check_cancel=cancel_after_first_wait,
        )

    page.wait_for_timeout.assert_called_once_with(250)
