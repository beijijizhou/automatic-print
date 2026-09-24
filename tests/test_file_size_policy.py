from pathlib import Path


LEGACY_TEST_LINE_LIMITS = {
    'test_automated_layout.py': 285,
    'test_developer_mode.py': 269,
    'test_haloo_completed_batches.py': 431,
    'test_machine_status.py': 272,
    'test_marker_examples.py': 264,
    'test_nested_batches.py': 285,
    'test_riin_admin_entry.py': 358,
    'test_s2b_batch_info.py': 366,
    'test_s2b_downloads.py': 263,
    'test_shared_knife_workflow.py': 460,
    'test_update_flow.py': 260,
}

LEGACY_APP_LINE_LIMITS = {
    'automatic_print/automation/api/s2b/production/downloads.py': 224,
    'automatic_print/automation/browser/batches.py': 263,
    'automatic_print/automation/browser/session.py': 235,
    'automatic_print/automation/transfer/downloads.py': 225,
    'automatic_print/batch_ui/platform/actions.py': 210,
    'automatic_print/batch_ui/platform/completed.py': 210,
    'automatic_print/batch_ui/task/actions.py': 227,
    'automatic_print/batch_ui/task/worker.py': 260,
    'automatic_print/ui/batch_folder_selection.py': 216,
    'automatic_print/ui/cutter_settings.py': 202,
    'automatic_print/ui/generation_preview.py': 214,
    'automatic_print/ui/machine_status_board.py': 232,
}


def test_application_files_follow_modularity_budget() -> None:
    root = Path(__file__).parents[1]
    oversized = []
    for path in (root / 'automatic_print').rglob('*.py'):
        relative = path.relative_to(root).as_posix()
        count = len(path.read_text(encoding='utf-8').splitlines())
        limit = LEGACY_APP_LINE_LIMITS.get(relative, 200)
        if count > limit:
            oversized.append(f'{relative}: {count} > {limit}')
    assert not oversized, '模块超过行数预算：\n' + '\n'.join(oversized)


def test_test_files_stay_cohesive() -> None:
    root = Path(__file__).parents[1]
    oversized = []
    for path in (root / 'tests').rglob('*.py'):
        count = len(path.read_text(encoding='utf-8').splitlines())
        limit = LEGACY_TEST_LINE_LIMITS.get(path.name, 250)
        if count > limit:
            oversized.append(f'{path.relative_to(root)}: {count} > {limit}')
    assert not oversized, '测试文件超过已有行数上限：\n' + '\n'.join(oversized)
