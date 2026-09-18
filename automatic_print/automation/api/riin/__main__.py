"""Standalone RIIN controller; each invocation executes one named operation."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .desktop import (
    accessible_inventory, dialog_inventory, import_menu, open_import, open_output,
    select_document, submit_import, window_inventory,
)
from .dialogs import acknowledge_import_errors, cancel_import, confirm_import
from .elevation import is_administrator, launch_elevated
from .window_control import probe_riin
from .output import begin_file_output, inspect_printexp, load_printexp, new_document, save_print_file
from .workflow import automate_layout_to_prn


def main(argv=None):
    parser = argparse.ArgumentParser(description='RIIN独立管理员控制入口')
    parser.add_argument('operation', choices=('automate-layout', 'inspect', 'open-import', 'import', 'confirm-import', 'cancel-import', 'import-menu', 'acknowledge-import-errors', 'select-document', 'open-output', 'begin-file-output', 'save-print-file', 'inspect-printexp', 'load-printexp', 'new-document'))
    parser.add_argument('--document')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--chunk-index', type=int, default=0)
    parser.add_argument('--elevate', action='store_true')
    args = parser.parse_args(argv)
    report_path = args.report.resolve()
    if args.operation == 'import' and not args.source:
        parser.error(f'{args.operation}需要--source来源目录。')
    if args.operation == 'automate-layout' and not (args.source or args.manifest):
        parser.error('automate-layout需要--source或--manifest。')
    if args.operation == 'automate-layout' and not args.output:
        parser.error('automate-layout需要--output输出文件。')
    if args.elevate and not is_administrator():
        forwarded = [args.operation, '--report', str(report_path)]
        if args.source:
            forwarded += ['--source', str(args.source.resolve())]
        if args.manifest:
            forwarded += ['--manifest', str(args.manifest.resolve())]
        if args.chunk_index:
            forwarded += ['--chunk-index', str(args.chunk_index)]
        if args.document:
            forwarded += ['--document', args.document]
        if args.output:
            forwarded += ['--output', str(args.output.resolve())]
        launch_elevated(forwarded)
        print('已请求Windows管理员授权；结果写入：' + str(report_path))
        return 0
    result = {'operation': args.operation, 'administrator': is_administrator()}
    try:
        if not result['administrator']:
            raise PermissionError('请使用--elevate启动独立控制入口。')
        probe = probe_riin(activate=False)
        if probe.error:
            raise RuntimeError(probe.error)
        # Match the native RIIN frame, excluding terminals and diagnostic dialogs.
        windows = [w for w in probe.windows if w.class_name.startswith('Afx:')
                   and w.title.endswith(' - RIIN')]
        if len(windows) != 1:
            raise RuntimeError(f'应找到一个RIIN主窗口，实际找到{len(windows)}个。')
        result.update(window=asdict(windows[0]), controls=window_inventory(windows[0].handle))
        if args.operation == 'automate-layout':
            files = None
            if args.manifest:
                files = json.loads(args.manifest.read_text(encoding='utf-8'))
            source = args.source or args.manifest.parent
            result['automation'] = automate_layout_to_prn(
                windows[0].handle, windows[0].process_id, source, args.output, files)
        elif args.operation == 'open-import':
            result['dialogs'] = open_import(windows[0].handle)
        elif args.operation == 'import':
            result['import'] = submit_import(windows[0].process_id, args.source, args.chunk_index)
        elif args.operation == 'confirm-import':
            result['action'] = confirm_import(windows[0].process_id)
        elif args.operation == 'cancel-import':
            result['action'] = cancel_import(windows[0].process_id)
        elif args.operation == 'import-menu':
            result['action'] = import_menu(windows[0].handle)
        elif args.operation == 'acknowledge-import-errors':
            result['action'] = acknowledge_import_errors(windows[0].process_id)
        elif args.operation == 'open-output':
            result['action'] = open_output(windows[0].handle)
        elif args.operation == 'select-document':
            result['action'] = select_document(windows[0].handle, args.document)
        elif args.operation == 'begin-file-output':
            result['action'] = begin_file_output(windows[0].process_id)
        elif args.operation == 'save-print-file':
            result['action'] = save_print_file(windows[0].process_id, args.output)
        elif args.operation == 'inspect-printexp':
            result['printexp'] = inspect_printexp()
        elif args.operation == 'new-document':
            result['action'] = new_document(windows[0].handle)
        elif args.operation == 'load-printexp':
            result['action'] = load_printexp(args.output)
        else:
            result['accessible_controls'] = accessible_inventory(windows[0].handle)
            result['dialogs'] = dialog_inventory(windows[0].process_id)
        result['ok'] = True
    except Exception as exc:
        import traceback
        result.update(ok=False, error=str(exc), traceback=traceback.format_exc())
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
