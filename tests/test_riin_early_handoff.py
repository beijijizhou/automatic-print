"""RIIN may hand a growing PRN to PrintExp once real progress begins."""

import pytest

from automatic_print.automation.api.riin import output, workflow


def test_wait_requires_positive_progress_and_more_than_placeholder(tmp_path, monkeypatch):
    target = tmp_path / 'batch.prn'
    target.write_bytes(b'x' * 48)
    polls = []

    def task(_target):
        polls.append(len(polls) + 1)
        if len(polls) == 3:
            target.write_bytes(b'prn' * 500)
        return {'state': '正在打印...',
                'percent': ('0%', '1%', '1%')[len(polls) - 1]}

    monkeypatch.setattr(output, 'riin_output_task', task)
    monkeypatch.setattr(output.time, 'sleep', lambda _seconds: None)
    result = output.wait_for_print_file(target, timeout=10)

    assert polls == [1, 2, 3]
    assert result['state'] == 'prn_writing'
    assert result['bytes'] == 1500
    assert result['riin_task']['percent'] == '1%'


def test_stable_file_without_exact_riin_task_is_not_handed_off(tmp_path, monkeypatch):
    target = tmp_path / 'batch.prn'
    target.write_bytes(b'prn' * 500)
    times = iter((0, 0.5, 1.5))
    monkeypatch.setattr(output, 'riin_output_task', lambda _target: None)
    monkeypatch.setattr(output.time, 'monotonic', lambda: next(times))
    monkeypatch.setattr(output.time, 'sleep', lambda _seconds: None)

    with pytest.raises(TimeoutError):
        output.wait_for_print_file(target, timeout=1)


def test_workflow_loads_early_prn_and_reports_writing(tmp_path, monkeypatch):
    image = tmp_path / 'a.png'
    image.write_bytes(b'png')
    target = tmp_path / 'batch.prn'
    calls = []
    monkeypatch.setattr(workflow.desktop, 'import_chunks', lambda _paths: [[image]])
    monkeypatch.setattr(workflow.riin_output, 'new_document',
                        lambda _handle: {'title': '未命名-12'})
    monkeypatch.setattr(workflow.desktop, 'open_import', lambda _handle: {})
    monkeypatch.setattr(workflow.desktop, 'submit_import_paths',
                        lambda *_args: {})
    monkeypatch.setattr(workflow, 'confirm_import', lambda _pid: {})
    monkeypatch.setattr(workflow.desktop, 'select_document', lambda *_args: {})
    monkeypatch.setattr(workflow.desktop, 'open_output', lambda _handle: {})
    monkeypatch.setattr(workflow.riin_output, 'begin_file_output',
                        lambda _pid: {})
    monkeypatch.setattr(workflow.riin_output, 'save_print_file',
                        lambda *_args: {})
    monkeypatch.setattr(workflow.riin_output, 'wait_for_print_file',
                        lambda _target: {'state': 'prn_writing', 'bytes': 1500,
                                         'riin_task': {'percent': '1%'}})
    monkeypatch.setattr(workflow.riin_output, 'load_printexp',
                        lambda _target: calls.append('loaded') or
                        {'state': 'printexp_loaded'})

    result = workflow.automate_layout_to_prn(
        10, 20, tmp_path, target, paths=[image])

    assert calls == ['loaded']
    assert result['state'] == 'completed'
    assert result['riin_complete'] is False
    assert result['riin_task']['percent'] == '1%'
