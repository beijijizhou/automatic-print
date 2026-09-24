import pytest

from automatic_print.automation.api.printerexp.state_machine import (
    CLEAN_RESUME, PAUSED, PAUSE_PRINT, PRINTING, READY, START_PRINT,
    control_allowed, inspect_printer_state, project_printer_state,
    require_control, transition_path,
)


@pytest.mark.parametrize(
    ("facts", "expected"),
    [
        ({"status_text": "正在清洗", "pause_enabled": True, "pause_caption": "暂停",
          "print_enabled": False}, "cleaning"),
        ({"status_text": "打印暂停", "pause_enabled": True, "pause_caption": "继续",
          "print_enabled": False}, PAUSED),
        ({"status_text": "正在打印", "pause_enabled": True, "pause_caption": "暂停",
          "print_enabled": False}, PRINTING),
        ({"status_text": "待打印", "pause_enabled": False, "pause_caption": "",
          "print_enabled": True, "task_loaded": True}, READY),
    ],
)
def test_native_facts_have_one_canonical_state_interpreter(facts, expected):
    assert inspect_printer_state(**facts) == expected


def test_projection_and_control_rules_share_the_same_states():
    assert project_printer_state(READY) == ("idle", "PrintExp待打印")
    assert project_printer_state(PAUSED) == ("running", "PrintExp已暂停")
    assert transition_path(START_PRINT, PAUSED) == (PRINTING,)
    assert transition_path(CLEAN_RESUME, PRINTING) == (PAUSED, "cleaning", PRINTING)


def test_start_requires_verified_exact_task_facts():
    facts = {"progress": 0, "task_name_verified": True, "batch_name": "job.prn"}
    assert control_allowed(START_PRINT, READY, **facts)
    assert not control_allowed(START_PRINT, READY, **{**facts, "progress": 1})
    assert not control_allowed(START_PRINT, READY, **{**facts, "task_name_verified": False})
    assert control_allowed(START_PRINT, PAUSED, **{**facts, "progress": 42})
    assert not control_allowed(START_PRINT, PAUSED, **{**facts, "progress": 100})


def test_invalid_transitions_are_rejected_centrally():
    assert not control_allowed(PAUSE_PRINT, PAUSED)
    assert not control_allowed(CLEAN_RESUME, READY)
    with pytest.raises(RuntimeError, match="不是正在打印"):
        require_control(PAUSE_PRINT, READY)
