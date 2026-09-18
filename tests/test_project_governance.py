from pathlib import Path
import json


ROOT = Path(__file__).parents[1]


def test_governance_documents_exist_and_are_current_state_documents():
    names = {
        'BUSINESS_RULES.md', 'CURRENT_STATE.md', 'FUNCTION_CATALOG.md',
        'PROJECT_RULES.md',
    }
    assert names <= {path.name for path in (ROOT/'docs').glob('*.md')}
    assert not (ROOT/'docs'/'hard-requirements.md').exists()


def test_agent_guide_defines_reuse_and_push_gates():
    guide = (ROOT/'AGENTS.md').read_text(encoding='utf-8')
    for rule in ('git ls-files', 'FUNCTION_CATALOG.md', '100–200',
                 '已运行的针对性测试失败时禁止推送', 'automation/api/<provider>/'):
        assert rule in guide


def test_windows_quality_gate_runs_complete_suite():
    workflow = (ROOT/'.github/workflows/quality-gate.yml').read_text(encoding='utf-8')
    assert 'windows-latest' in workflow
    assert 'python -m pytest -q' in workflow


def test_self_hosted_acceptance_is_pinned_and_keeps_batch_failures_independent():
    workflow = (ROOT/'.github/workflows/windows-self-hosted.yml').read_text(encoding='utf-8')
    runner = (ROOT/'windows/run-real-batch-suite.ps1').read_text(encoding='utf-8')
    manifest = json.loads((ROOT/'windows/real-batch-suite.json').read_text(encoding='utf-8'))
    assert 'Record immutable tested commit' in workflow
    assert 'run-real-batch-suite.ps1' in workflow
    assert 'AUTOMATIC_PRINT_S2B_BATCH_INFO_KEY' in workflow
    assert 'foreach ($batch in $batches)' in runner
    assert 'foreach ($cacheState in $batch.passes)' in runner
    assert 'suite-summary.json' in runner
    performance = next(row for row in manifest['batches']
                       if row['id'] == 'longfeng-performance-609172109020')
    assert performance['expected_images'] == 200
    assert performance['passes'] == ['cold', 'hot']
    assert performance['max_generation_seconds'] == 30
    assert performance['output_parts'] == 8
    assert performance['save_parallelism'] == 8
    assert len(manifest['batches']) >= 10
    assert sum(row['platform'] == 'Haloo' for row in manifest['batches']) >= 3
    assert {'Haloo', '隆丰', '莆田', 'S2B'} <= {
        row['platform'] for row in manifest['batches']
    }
