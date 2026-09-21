import pytest

from automatic_print.layout_engine.intake.discovery.batch_discovery import scan_batches
from test_nested_batches import tree


def test_unreadable_branch_does_not_block_other_batches_and_scan_can_cancel(
        tmp_path, monkeypatch):
    import automatic_print.layout_engine.intake.discovery.batch_discovery as discovery
    from automatic_print.runtime.cancellation import Cancellation, TaskCancelled
    root = tmp_path/'HL'
    tree(root)
    original = discovery.scandir

    def entries(path):
        if path == root/'白色':
            raise PermissionError('cannot read branch')
        return original(path)

    monkeypatch.setattr(discovery, 'scandir', entries)
    scan = scan_batches(root)
    assert len(scan['batches']) == 2 and len(scan['errors']) == 1
    assert scan['errors'][0]['folder'] == str(root/'白色')
    cancellation = Cancellation()
    cancellation.request()
    with pytest.raises(TaskCancelled):
        scan_batches(root, cancellation=cancellation)
