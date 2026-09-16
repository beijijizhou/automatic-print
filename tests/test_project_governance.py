from pathlib import Path


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
