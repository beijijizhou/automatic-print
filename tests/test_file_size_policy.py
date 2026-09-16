from pathlib import Path


LEGACY_LIMITS = {
    'automatic_print/automation/erp_api.py': 234,
    'automatic_print/automation/rule_batches.py': 241,
    'automatic_print/layout_engine/service.py': 220,
}


def test_application_files_follow_modularity_budget() -> None:
    root = Path(__file__).parents[1]
    oversized = []
    for path in (root / 'automatic_print').rglob('*.py'):
        relative = path.relative_to(root).as_posix()
        count = len(path.read_text(encoding='utf-8').splitlines())
        limit = LEGACY_LIMITS.get(relative, 200)
        if count > limit:
            oversized.append(f'{relative}: {count} > {limit}')
    assert not oversized, '模块超过行数预算：\n' + '\n'.join(oversized)


def test_test_files_stay_cohesive() -> None:
    root = Path(__file__).parents[1]
    oversized = []
    for path in (root / 'tests').rglob('*.py'):
        count = len(path.read_text(encoding='utf-8').splitlines())
        if count > 250:
            oversized.append(f'{path.relative_to(root)}: {count}')
    assert not oversized, '测试文件超过250行：\n' + '\n'.join(oversized)
