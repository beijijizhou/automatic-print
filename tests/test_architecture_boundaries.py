import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]


def modules(package):
    return sorted((ROOT/'automatic_print'/package).glob('*.py'))


def test_new_domain_packages_stay_small_and_cohesive():
    for package in (
        'controllers', 'history', 'batch_ui/shell',
        'layout_engine/text', 'automation/api/erp', 'ui/workbench',
    ):
        paths = modules(package)
        assert len(paths) <= 5, f'{package} 顶层模块超过5个，应按职责建立子包'
        oversized = [path.name for path in paths
                     if len(path.read_text(encoding='utf-8').splitlines()) > 200]
        assert not oversized, f'{package} 中存在超过200行的模块：{oversized}'


def test_controllers_do_not_import_widgets():
    offenders = [path.name for path in modules('controllers')
                 if 'PySide6.QtWidgets' in path.read_text(encoding='utf-8')]
    assert not offenders, f'控制器不得直接操作界面控件：{offenders}'


def test_main_window_only_composes_visible_surfaces():
    path = ROOT/'automatic_print/ui/main_window.py'
    text = path.read_text(encoding='utf-8')
    assert len(text.splitlines()) <= 110
    assert 'build_settings(self)' in text
    assert 'build_activity(self)' in text
    assert 'build_home(self)' in text
    assert 'QFormLayout' not in text
    assert 'QTabWidget' not in text


def test_core_layers_do_not_import_ui():
    offenders = []
    for package in ('controllers', 'history', 'layout_engine', 'automation'):
        for path in (ROOT/'automatic_print'/package).rglob('*.py'):
            text = path.read_text(encoding='utf-8')
            if 'automatic_print.ui' in text or 'from ..ui' in text or 'from ...ui' in text:
                offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, f'核心层反向依赖UI：{offenders}'


def test_no_exact_copy_pasted_function_bodies():
    bodies = {}
    for path in (ROOT/'automatic_print').rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and len(node.body) >= 3:
                body = ast.dump(ast.Module(body=node.body, type_ignores=[]),
                                include_attributes=False)
                bodies.setdefault(body, []).append(
                    f'{path.relative_to(ROOT)}:{node.lineno}:{node.name}')
    duplicates = [locations for locations in bodies.values()
                  if len({item.rsplit(':', 2)[0] for item in locations}) > 1]
    assert not duplicates, f'发现跨模块完全重复实现：{duplicates}'
