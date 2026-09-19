import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]


def modules(package):
    return sorted(path for path in (ROOT/'automatic_print'/package).glob('*.py')
                  if path.name != '__init__.py')


def test_new_domain_packages_stay_small_and_cohesive():
    for package in (
        'controllers', 'history', 'batch_ui/local', 'batch_ui/platform',
        'batch_ui/task', 'batch_ui/shell',
        'layout_engine/cutting/geometry',
        'layout_engine/cutting/validation', 'layout_engine/diagnostics',
        'layout_engine/intake/discovery', 'layout_engine/intake/metadata',
        'layout_engine/intake/preparation', 'layout_engine/labeling/base',
        'layout_engine/labeling/markers', 'layout_engine/labeling/platform',
        'layout_engine/labeling/text', 'layout_engine/measurement',
        'layout_engine/orders', 'layout_engine/output',
        'layout_engine/pipeline', 'layout_engine/domain',
        'layout_engine/planning/base', 'layout_engine/planning/cache',
        'layout_engine/planning/columns', 'layout_engine/planning/film',
        'layout_engine/planning/packing',
        'layout_engine/planning/rotation', 'layout_engine/planning/zones',
        'layout_engine/rendering', 'layout_engine/rendering/engines',
        'layout_engine/rendering/png',
        'layout_engine/rendering/storage', 'layout_engine/reporting',
        'automation/batches', 'automation/browser', 'automation/providers',
        'automation/transfer', 'automation/workflows', 'automation/api/erp',
        'runtime', 'updates',
        'automation/api/s2b', 'automation/api/s2b/metadata',
        'automation/api/s2b/production', 'ui/workbench',
        'ui/workbench/overview',
        'ui/workbench/preferences',
        'ui/workbench/generation',
        'ui/previews', 'ui/previews/markers', 'ui/previews/runtime',
        'ui/settings', 'ui/settings/output',
    ):
        paths = modules(package)
        assert len(paths) <= 5, f'{package} 顶层模块超过5个，应按职责建立子包'
        oversized = [path.name for path in paths
                     if len(path.read_text(encoding='utf-8').splitlines()) > 200]
        assert not oversized, f'{package} 中存在超过200行的模块：{oversized}'


def test_layout_engine_root_is_only_a_small_facade():
    assert not modules('layout_engine')


def test_application_root_contains_only_startup_entry_points():
    assert {path.name for path in modules('')} == {'__main__.py', 'app.py'}


def test_desktop_entry_points_follow_runtime_module_moves():
    import dev
    import run_app

    assert callable(dev.main)
    assert callable(run_app.main)
    assert callable(run_app.run_with_crash_logging)


def test_packaged_entry_point_loads_ui_inside_crash_guard():
    launchers = {
        ROOT/'run_app.py': (
            'from automatic_print.runtime.crash_logging',
            'from automatic_print.app import run',
        ),
        ROOT/'automatic_print/__main__.py': (
            'from .runtime.crash_logging', 'from .app import run',
        ),
    }
    for path, (guard, ui) in launchers.items():
        source = path.read_text(encoding='utf-8')
        assert source.index(guard) < source.index(ui)
        assert 'run_with_crash_logging(_load_and_run)' in source


def test_automation_root_is_only_a_public_facade():
    assert not modules('automation')


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


def test_batch_overview_matches_visible_ui_regions():
    facade = ROOT/'automatic_print/ui/label_quick_panel.py'
    assert len(facade.read_text(encoding='utf-8').splitlines()) <= 10
    package = ROOT/'automatic_print/ui/workbench/overview'
    assert {path.name for path in package.glob('*.py')} == {
        '__init__.py', 'panel.py', 'label_controls.py', 'preview.py', 'bindings.py'
    }


def test_print_preferences_separate_state_directions_and_actions():
    package = ROOT/'automatic_print/ui/workbench/preferences'
    assert {path.name for path in package.glob('*.py')} == {
        '__init__.py', 'mixin.py', 'load.py', 'save.py', 'actions.py'
    }


def test_generation_ui_separates_start_progress_and_results():
    package = ROOT/'automatic_print/ui/workbench/generation'
    assert {path.name for path in package.glob('*.py')} == {
        '__init__.py', 'mixin.py', 'start.py', 'progress.py', 'results.py'
    }


def test_batch_workbench_matches_navigation_and_task_boundaries():
    package = ROOT/'automatic_print/batch_ui'
    assert {path.name for path in package.glob('*.py')} == {
        '__init__.py', 'dialog.py'
    }
    assert {path.name for path in (package/'local').glob('*.py')} == {
        '__init__.py', 'actions.py', 'page.py', 'processing.py', 'scanning.py'
    }
    assert {path.name for path in (package/'platform').glob('*.py')} == {
        '__init__.py', 'actions.py', 'cache.py', 'generation.py', 'pages.py', 'completed.py'
    }
    assert {path.name for path in (package/'task').glob('*.py')} == {
        '__init__.py', 'actions.py', 'worker.py', 'reads.py',
        'automatic_print.py'
    }


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
