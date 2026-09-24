from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
from .versioning import release_display

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REMOTE_URLS = {'https://github.com/beijijizhou/automatic-print.git',
               'https://github.com/beijijizhou/automatic-print',
               'git@github.com:beijijizhou/automatic-print.git'}
LOCK_NAME = '.update-in-progress'


def source_install(root=PROJECT_ROOT):
    return not getattr(sys, 'frozen', False) and (root/'.git').exists()


@dataclass(frozen=True)
class SourceUpdateInfo:
    current: str
    target: str
    version: str
    release_date: str
    commits: int
    repair: bool = False
    release_iteration: int = 0
    rollback: bool = False

    @property
    def needs_update(self):
        return self.current != self.target or self.repair

    @property
    def display_version(self):
        return release_display(self.version, self.release_date, self.release_iteration)


@dataclass(frozen=True)
class SourceVersion:
    revision: str
    version: str
    release_date: str
    release_iteration: int = 0

    @property
    def display_version(self):
        return release_display(self.version, self.release_date, self.release_iteration)


class SourceUpdater:
    def __init__(self, root=PROJECT_ROOT, progress=None):
        self.root = Path(root)
        self.progress = progress or (lambda text: None)
        self.git = shutil.which('git')
        if not self.git and os.name == 'nt':
            for base in ('ProgramFiles', 'LOCALAPPDATA'):
                relative = 'Git/cmd/git.exe' if base == 'ProgramFiles' else 'Programs/Git/cmd/git.exe'
                candidate = Path(os.environ.get(base, ''))/relative
                if candidate.is_file():
                    self.git = str(candidate)
                    break
        if not self.git:
            raise ValueError('未找到代码更新工具，请先运行一键安装/更新指令。')

    def run(self, args, timeout=60):
        environment = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never',
                           PYTHONUTF8='1')
        try:
            result = subprocess.run(args, cwd=self.root, env=environment, timeout=timeout,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    encoding='utf-8', errors='replace',
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except subprocess.TimeoutExpired:
            raise ValueError('更新操作超时，请检查网络后重试。') from None
        if result.returncode:
            raise ValueError('更新操作失败：'+result.stdout[-1200:])
        return result.stdout.strip()

    def git_run(self, *args):
        return self.run([self.git, *args])

    def validate(self):
        if not source_install(self.root):
            raise ValueError('当前不是源码安装，无法直接拉取代码。')
        if Path(self.git_run('rev-parse', '--show-toplevel')).resolve() != self.root.resolve():
            raise ValueError('安装目录与代码仓库不一致，更新已停止。')
        if self.git_run('remote', 'get-url', 'origin') not in REMOTE_URLS:
            raise ValueError('更新来源不是本项目官方仓库，更新已停止。')
        if self.git_run('branch', '--show-current') != 'main':
            raise ValueError('当前不在主分支，更新已停止以保护本地开发代码。')
        if self.git_run('status', '--porcelain', '--untracked-files=no'):
            raise ValueError('发现本地代码修改（已跟踪文件），更新已停止，不会覆盖。')

    def check(self, target=None):
        self.progress('正在检查安装目录及本地代码…')
        self.validate()
        self.progress('正在连接代码仓库，检查最新提交…')
        self.git_run('fetch', 'origin', 'main')
        current = self.git_run('rev-parse', 'HEAD')
        latest = self.git_run('rev-parse', 'refs/remotes/origin/main')
        selected = str(target or latest).strip().lower()
        if not re.fullmatch(r'[0-9a-f]{40}', selected):
            raise ValueError('目标源码提交号格式不正确。')
        self.git_run('merge-base', '--is-ancestor', selected, latest)
        self.git_run('merge-base', '--is-ancestor', current, latest)
        content = self.git_run('show', f'{selected}:automatic_print/__init__.py')
        metadata = _source_version(selected, content, self)
        forward = int(self.git_run('rev-list', '--count', f'{current}..{selected}'))
        backward = int(self.git_run('rev-list', '--count', f'{selected}..{current}'))
        if forward and backward:
            raise ValueError('当前版本与目标版本不在同一条main历史上。')
        return SourceUpdateInfo(
            current, selected, metadata.version, metadata.release_date,
            max(forward, backward), (self.root/LOCK_NAME).exists(),
            metadata.release_iteration, rollback=bool(backward),
        )

    def available_versions(self, limit=20):
        self.validate()
        self.progress('正在连接代码仓库，读取可回滚版本…')
        self.git_run('fetch', 'origin', 'main')
        latest = self.git_run('rev-parse', 'refs/remotes/origin/main')
        revisions = self.git_run(
            'log', f'--max-count={int(limit)}', '--format=%H', latest,
            '--', 'automatic_print/__init__.py',
        ).splitlines()
        versions = []
        for revision in revisions:
            content = self.git_run('show', f'{revision}:automatic_print/__init__.py')
            version = _source_version(revision, content, self)
            if _version_key(version.version) >= (0, 1, 393):
                versions.append(version)
        return versions

    def apply(self, info):
        self.progress('正在复核本地代码及待更新版本…')
        self.validate()
        if self.git_run('rev-parse', 'HEAD') != info.current:
            raise ValueError('本地版本已变化，请重新检查更新。')
        lock = self.root/LOCK_NAME
        lock.touch()
        # Leave the reload guard on failure: do not restart into incomplete dependencies.
        if info.rollback:
            self.progress('正在安全回滚到已确认的历史版本…')
            self.git_run('reset', '--keep', info.target)
        else:
            self.progress('正在拉取并应用已确认的新代码…')
            self.git_run('merge', '--ff-only', info.target)
        self.progress('正在检查和更新运行依赖，请稍候…')
        self.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                  '-r', str(self.root/'requirements.txt')], timeout=600)
        self.progress('代码和依赖更新完成，正在准备安全重启…')
        lock.unlink(missing_ok=True)
        return info


def _source_version(revision, content, updater):
    version = re.search(r'__version__\s*=\s*[\'"]([^\'"]+)', content)
    date = re.search(r'__release_date__\s*=\s*[\'"]([^\'"]+)', content)
    iteration = re.search(r'__release_iteration__\s*=\s*(\d+)', content)
    return SourceVersion(
        revision, version[1] if version else '待确认',
        date[1] if date else updater.git_run('show', '-s', '--format=%cs', revision),
        int(iteration[1]) if iteration else 0,
    )


def _version_key(value):
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)', str(value))
    return tuple(map(int, match.groups())) if match else (0, 0, 0)
