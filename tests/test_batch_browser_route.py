from unittest.mock import MagicMock, patch

from automatic_print.automation.browser.batches import _batch_page


def test_batch_page_uses_direct_url_when_sidebar_link_is_absent():
    target = (
        "https://longfeng.merchant.hihumbird.com/factory/fnsz-sale/"
        "produceManage/produceChainManage/productionBatch/index"
    )
    page = MagicMock()
    page.url = "https://longfeng.merchant.hihumbird.com/factory/home"
    page.get_by_text.return_value.count.return_value = 0
    page.locator.return_value.count.return_value = 0
    page.goto.side_effect = lambda url, **_kwargs: setattr(page, "url", url)
    browser = MagicMock(contexts=[MagicMock(pages=[page])])
    frame = MagicMock()
    frame.locator.return_value.count.return_value = 1
    messages = []

    with patch(
        "automatic_print.automation.browser.batches.open_authenticated_page",
        return_value=page,
    ), patch(
        "automatic_print.automation.browser.batches.production_batch_frame",
        return_value=frame,
    ):
        result = _batch_page(browser, target, progress=messages.append)

    assert result is page
    page.goto.assert_called_once_with(
        target, wait_until="domcontentloaded", timeout=30_000,
    )
    assert any("直接打开生产批次地址" in message for message in messages)
