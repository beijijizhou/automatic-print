from unittest.mock import MagicMock, patch

from automatic_print.automation.batches.local import discover_local_batches
from automatic_print.batch_ui.local.processing import _batch_folders
from automatic_print.automation.browser.session import open_authenticated_page, show_debug_browser


def test_nested_archive_batch_is_processed_once(tmp_path):
    root = tmp_path / 'Haloo'
    outer = root / 'BATCHES' / '609180613013'
    inner = outer / outer.name
    inner.mkdir(parents=True)
    (inner / 'order-front.png').touch()
    (outer / 'order-back.png').touch()
    preview = root / 'PREVIEW' / outer.name
    preview.mkdir(parents=True)
    (preview / 'preview.png').touch()
    assert _batch_folders(root, [outer.name]) == [outer]
    batches = discover_local_batches(tmp_path, 'Haloo')
    assert len(batches) == 1
    assert batches[0].image_count == 2


def test_hidden_erp_frame_can_wait_for_attachment():
    url = 'https://haloopod.merchant.hihumbird.com/factory/productionBatch/index'
    page = MagicMock()
    page.url = url
    browser = MagicMock()
    browser.contexts = [MagicMock(pages=[page])]
    page.locator.return_value.first.count.return_value = 1
    assert open_authenticated_page(browser, url, 'iframe', ready_state='attached') is page


def test_delayed_login_redirect_is_consumed_in_one_open_call():
    target = ('https://longfeng.merchant.hihumbird.com/factory/'
              'fnsz-sale/produceManage/produceItemsManage')

    class Locator:
        @property
        def first(self):
            return self

        def count(self):
            return int(page.ready)

        def is_visible(self):
            return page.ready

    class Page:
        def __init__(self):
            self.url = target
            self.ready = False
            self.context = MagicMock()
            self.waits = 0
            self.goto_calls = []

        def locator(self, _selector):
            return Locator()

        def wait_for_timeout(self, _milliseconds):
            self.waits += 1
            if self.waits == 1:
                self.url = 'https://longfeng.merchant.hihumbird.com/login'
            elif self.waits == 2:
                self.url = 'https://longfeng.merchant.hihumbird.com/home'

        def goto(self, url, **_kwargs):
            self.goto_calls.append(url)
            self.url = url
            self.ready = True

    page = Page()
    browser = MagicMock()
    browser.contexts = [MagicMock(pages=[page])]
    messages = []
    with patch('automatic_print.automation.browser.session.time.monotonic',
               side_effect=range(100, 120)):
        result = open_authenticated_page(
            browser, target, '.search-container', progress=messages.append
        )

    assert result is page
    assert page.goto_calls == [target]
    assert sum('完成登录' in message for message in messages) == 1
    assert any('登录成功' in message for message in messages)


def test_show_debug_browser_foregrounds_existing_login_page():
    target = ('https://longfeng.merchant.hihumbird.com/factory/'
              'fnsz-sale/produceManage/produceItemsManage')
    page = MagicMock(url='https://longfeng.merchant.hihumbird.com/factory/login')
    browser = MagicMock(contexts=[MagicMock(pages=[page])])
    playwright = object()
    context = MagicMock()
    context.__enter__.return_value = playwright
    messages = []

    with patch('playwright.sync_api.sync_playwright', return_value=context), \
         patch('automatic_print.automation.browser.session.connect_debug_chrome',
               return_value=browser) as connect:
        result = show_debug_browser(target, progress=messages.append)

    connect.assert_called_once()
    page.bring_to_front.assert_called_once_with()
    page.goto.assert_not_called()
    assert result.endswith('/factory/login')
    assert any('已显示' in message for message in messages)
