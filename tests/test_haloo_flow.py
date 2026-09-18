from unittest.mock import MagicMock

from automatic_print.automation.batches.local import discover_local_batches
from automatic_print.batch_ui.local.processing import _batch_folders
from automatic_print.automation.browser.session import open_authenticated_page


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
    assert open_authenticated_page(browser, url, 'iframe', ready_state='attached') is page
    page.locator.return_value.first.wait_for.assert_called_once_with(
        state='attached', timeout=30_000)
