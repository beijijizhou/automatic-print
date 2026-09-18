from pathlib import Path
import subprocess
import sys
import pytest

from automatic_print.updates import source


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.STDOUT).decode().strip()


@pytest.fixture
def repositories(tmp_path, monkeypatch):
    remote, seed, client = [tmp_path/name for name in ('remote.git', 'seed', 'client')]
    remote.mkdir(); seed.mkdir()
    git(remote, 'init', '--bare')
    git(seed, 'init', '-b', 'main')
    git(seed, 'config', 'user.email', 'test@example.com')
    git(seed, 'config', 'user.name', 'Test')
    # Tests own this disposable repository; do not inherit workstation hooks
    # that protect a real checkout's main branch.
    git(seed, 'config', 'core.hooksPath', '')
    (seed/'automatic_print').mkdir()
    (seed/'automatic_print/__init__.py').write_text('__version__ = "0.1.1"\n__release_date__ = "2026-09-13"\n')
    (seed/'requirements.txt').write_text('')
    (seed/'.gitignore').write_text('.update-in-progress\n')
    git(seed, 'add', '.'); git(seed, 'commit', '-m', 'initial')
    git(seed, 'remote', 'add', 'origin', str(remote)); git(seed, 'push', 'origin', 'main')
    subprocess.check_output(['git', 'clone', '--branch', 'main', str(remote), str(client)], stderr=subprocess.STDOUT)
    monkeypatch.setattr(source, 'REMOTE_URLS', {str(remote)})
    return seed, client


def publish(seed):
    (seed/'automatic_print/__init__.py').write_text('__version__ = "0.1.2"\n__release_date__ = "2026-09-14"\n__release_iteration__ = 2\n')
    git(seed, 'add', '.'); git(seed, 'commit', '-m', 'update'); git(seed, 'push', 'origin', 'main')


def test_check_and_apply_fast_forward_without_installer(repositories, monkeypatch):
    seed, client = repositories
    stages = []
    updater = source.SourceUpdater(client, stages.append)
    assert not updater.check().needs_update
    publish(seed)
    info = updater.check()
    assert info.needs_update and info.commits == 1
    assert info.display_version == '2026-09-14 · 第02次更新'
    assert info.version == '0.1.2' and info.release_iteration == 2
    original, commands = updater.run, []
    def run(args, **kwargs):
        commands.append(args)
        if args[:3] == [sys.executable, '-m', 'pip']:
            assert (client/source.LOCK_NAME).exists()
            return ''
        return original(args, **kwargs)
    monkeypatch.setattr(updater, 'run', run)
    updater.apply(info)
    assert git(client, 'rev-parse', 'HEAD') == info.target
    assert not (client/source.LOCK_NAME).exists()
    assert any('pip' in args for args in commands)
    assert any('依赖' in stage for stage in stages)


def test_local_changes_and_wrong_branch_are_protected(repositories):
    seed, client = repositories
    publish(seed)
    updater = source.SourceUpdater(client)
    info = updater.check()
    path = client/'requirements.txt'
    path.write_text('local user changes')
    with pytest.raises(ValueError, match='本地代码修改'):
        updater.apply(info)
    assert path.read_text() == 'local user changes'
    path.write_text('')
    git(client, 'checkout', '-b', 'local-development')
    with pytest.raises(ValueError, match='主分支'):
        updater.check()


def test_untracked_local_files_do_not_block_or_get_removed(repositories, monkeypatch):
    seed, client = repositories
    publish(seed)
    untracked = client/'.tmp-local-acceptance'/'result.txt'
    untracked.parent.mkdir()
    untracked.write_text('keep me')
    updater = source.SourceUpdater(client)
    info = updater.check()
    original = updater.run
    monkeypatch.setattr(
        updater, 'run',
        lambda args, **kwargs: ''
        if args[:3] == [sys.executable, '-m', 'pip']
        else original(args, **kwargs))
    updater.apply(info)
    assert untracked.read_text() == 'keep me'
    assert git(client, 'rev-parse', 'HEAD') == info.target


def test_dependency_failure_keeps_guard_and_can_be_retried(repositories, monkeypatch):
    seed, client = repositories
    publish(seed)
    updater = source.SourceUpdater(client)
    info = updater.check()
    original = updater.run
    def fail_pip(args, **kwargs):
        if 'pip' in args:
            raise ValueError('dependency failed')
        return original(args, **kwargs)
    monkeypatch.setattr(updater, 'run', fail_pip)
    with pytest.raises(ValueError, match='dependency failed'):
        updater.apply(info)
    assert (client/source.LOCK_NAME).exists()
    repaired = updater.check()
    assert repaired.current == repaired.target and repaired.needs_update
    monkeypatch.setattr(updater, 'run', lambda args, **kwargs: '' if 'pip' in args else original(args, **kwargs))
    updater.apply(repaired)
    assert not (client/source.LOCK_NAME).exists()
