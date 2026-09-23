"""Contracts for the bounded, user-elevated RIIN entry point."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from automatic_print.automation.api.riin.__main__ import main
from automatic_print.automation.api.riin.desktop_controls.desktop import open_output, png_import_paths
from automatic_print.automation.api.riin.desktop_controls.dialogs import cancel_crop_warning
from automatic_print.automation.api.riin.desktop_controls.dialogs import confirm_import
from automatic_print.automation.api.riin.output import (
    load_printexp, wait_for_print_file,
)
from automatic_print.automation.api.riin.jobs import generate_prn
from automatic_print.automation.api.riin.workflow import automate_layout_to_prn


class AdminEntryTests(unittest.TestCase):
    def test_import_settings_selects_and_verifies_original_size(self):
        desktop = MagicMock()
        dialog = desktop.window.return_value
        original = MagicMock()
        original.window_text.return_value = '按原图尺寸导入'
        original.class_name.return_value = 'Button'
        original.get_check_state.side_effect = [0, 1]
        dialog.descendants.return_value = [original]
        messages = []

        with patch('pywinauto.Desktop', return_value=desktop), \
             patch('automatic_print.automation.api.riin.desktop_controls.dialogs.time.sleep'):
            result = confirm_import(22, messages.append)

        original.click.assert_called_once_with()
        dialog.child_window.assert_called_once_with(
            title='确定', class_name='Button')
        dialog.child_window.return_value.click.assert_called_once_with()
        self.assertEqual(result['parameters'], '按原图尺寸导入')
        self.assertEqual(result['confirmation'], 'automatic')
        self.assertTrue(any('原图尺寸' in message for message in messages))

    def test_unrecognized_import_settings_waits_for_manual_confirmation(self):
        desktop = MagicMock()
        dialog = desktop.window.return_value
        scaled = MagicMock()
        scaled.window_text.return_value = '适合页面'
        scaled.class_name.return_value = 'Button'
        dialog.descendants.return_value = [scaled]
        messages = []

        with patch('pywinauto.Desktop', return_value=desktop):
            result = confirm_import(22, messages.append, manual_timeout=15)

        dialog.child_window.assert_not_called()
        dialog.wait_not.assert_called_once_with('visible', timeout=15)
        self.assertEqual(result['confirmation'], 'manual')
        self.assertTrue(any('手动选择原尺寸' in message for message in messages))

    def test_parent_ui_receives_manual_original_size_prompt(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            image = source / 'layout.png'
            image.write_bytes(b'png')
            output = source / 'layout.prn'
            state = {}
            messages = []

            def launch(arguments):
                report = Path(arguments[arguments.index('--report') + 1])
                state['report'] = report
                report.write_text(json.dumps({
                    'done': False,
                    'status': ('未识别到可验证的原尺寸选项；请在RIIN“导入图像设置”'
                               '窗口手动选择原尺寸并点击确定。'),
                }, ensure_ascii=False), encoding='utf-8')

            def finish(_seconds):
                state['report'].write_text(json.dumps({
                    'done': True,
                    'ok': True,
                    'automation': {'state': 'completed'},
                }), encoding='utf-8')

            with patch(
                'automatic_print.automation.api.riin.jobs.launch_elevated',
                side_effect=launch,
            ), patch(
                'automatic_print.automation.api.riin.jobs.time.sleep',
                side_effect=finish,
            ):
                result = generate_prn([image], output, messages.append)

            self.assertEqual(result['state'], 'completed')
            self.assertTrue(any('手动选择原尺寸' in message for message in messages))

    def test_crop_warning_cancel_requires_exact_destructive_message(self):
        desktop = MagicMock()
        found, dialog, message = MagicMock(), MagicMock(), MagicMock()
        found.class_name.return_value = '#32770'
        found.window_text.return_value = 'RIIN'
        found.is_visible.return_value = True
        message.window_text.return_value = (
            '图元超出画布，超出部分将被自动裁切，是否继续打印?'
        )
        found.descendants.return_value = [message]
        desktop.windows.return_value = [found]
        desktop.window.return_value = dialog
        with patch('pywinauto.Desktop', return_value=desktop):
            result = cancel_crop_warning(22)
        desktop.windows.assert_called_once_with(process=22)
        dialog.child_window.assert_called_once_with(
            title='取消', control_id=7, class_name='Button')
        dialog.child_window.return_value.click.assert_called_once_with()
        self.assertEqual(result['state'], 'unsafe_crop_cancelled')

    def test_prn_placeholder_waits_for_riin_task_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'batch.prn'
            target.write_bytes(b'x' * 48)
            states = iter(('等待打印...', '正在打印...', '打印完成',
                           '打印完成', '打印完成', '打印完成'))

            def task(_target):
                state = next(states)
                if state == '打印完成':
                    target.write_bytes(b'prn' * 500)
                return {'state': state, 'percent': '100%' if state == '打印完成' else '0%'}

            with patch(
                'automatic_print.automation.api.riin.output.riin_output_task',
                side_effect=task,
            ), patch('automatic_print.automation.api.riin.output.time.sleep'):
                result = wait_for_print_file(target, timeout=10)

            self.assertEqual(result['bytes'], 1500)
            self.assertEqual(result['riin_task']['state'], '打印完成')

    def test_printexp_load_is_verified_by_visible_task_name(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'batch.prn'
            target.write_bytes(b'prn')
            native_desktop = MagicMock()
            uia_desktop = MagicMock()
            main = MagicMock()
            native_dialog = MagicMock(handle=99)
            field = MagicMock()
            task, progress, copies = MagicMock(), MagicMock(), MagicMock()
            for control, text in (
                (task, target.name), (progress, '0.00%'), (copies, '0 / 1'),
            ):
                control.is_visible.return_value = True
                control.window_text.return_value = text
            main.process_id.return_value = 22
            main.descendants.return_value = [task, progress, copies]
            native_dialog.exists.return_value = True
            native_dialog.is_visible.return_value = True
            field.get_value.return_value = str(target.resolve())
            native_desktop.window.side_effect = [main, native_dialog]
            uia_desktop.window.return_value.child_window.return_value = field

            def desktop(backend):
                return native_desktop if backend == 'win32' else uia_desktop

            with patch('pywinauto.Desktop', side_effect=desktop):
                result = load_printexp(target)
            self.assertEqual(result['state'], 'printexp_loaded')
            self.assertEqual(result['task'], target.name)
            self.assertEqual(result['progress'], '0.00%')
            self.assertEqual(result['copies'], '0 / 1')

    def test_printexp_open_uses_window_message_without_pointer_focus(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'batch.prn'
            target.write_bytes(b'prn')
            native_desktop = MagicMock()
            uia_desktop = MagicMock()
            main, native_dialog, button, parent = (
                MagicMock(), MagicMock(handle=99), MagicMock(handle=88), MagicMock()
            )
            main.process_id.return_value = 22
            main.child_window.return_value = button
            button.parent.return_value = parent
            native_dialog.exists.return_value = False
            native_dialog.is_visible.side_effect = [False, True]
            field = MagicMock()
            field.get_value.return_value = str(target.resolve())
            task = MagicMock()
            task.is_visible.return_value = True
            task.window_text.return_value = target.name
            main.descendants.return_value = [task]
            native_desktop.window.side_effect = [main, native_dialog]
            uia_desktop.window.return_value.child_window.return_value = field

            def desktop(backend):
                return native_desktop if backend == 'win32' else uia_desktop

            with patch('pywinauto.Desktop', side_effect=desktop):
                result = load_printexp(target)
            main.set_focus.assert_not_called()
            parent.post_message.assert_called_once_with(0x0111, 5, button.handle)
            self.assertEqual(result['state'], 'printexp_loaded')

    def test_output_waits_for_riin_before_using_document_print_command(self):
        desktop = MagicMock()
        window = desktop.window.return_value
        with patch('pywinauto.Desktop', return_value=desktop):
            result = open_output(10)
        desktop.window.assert_called_once_with(handle=10)
        window.restore.assert_called_once_with()
        window.wait.assert_called_once_with('enabled ready', timeout=60)
        window.set_focus.assert_called_once_with()
        window.type_keys.assert_called_once_with('^p')
        self.assertEqual(result['entry'], 'Ctrl+P')

    def test_import_list_preserves_unicode_spaces_and_nested_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '批次 A').mkdir()
            image = root / '批次 A' / '图案 1.PNG'
            image.write_bytes(b'png')
            (root / 'report.txt').write_text('not an image')
            paths, selection = png_import_paths(root)
            self.assertEqual(paths, [image.resolve()])
            self.assertEqual(selection, '"' + str(image.resolve()) + '"')

    def test_empty_batch_does_not_submit_anything(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, '没有PNG'):
                png_import_paths(folder)

    def test_open_dialog_uses_input_fallback_when_message_click_is_ignored(self):
        from automatic_print.automation.api.riin.desktop_controls.desktop import (
            _submit_open_dialog,
        )

        dialog = MagicMock()
        button = dialog.child_window.return_value
        dialog.wait_not.side_effect = [RuntimeError('timed out'), None]

        _submit_open_dialog(dialog)

        button.click.assert_called_once_with()
        button.click_input.assert_called_once_with()
        self.assertEqual(dialog.wait_not.call_count, 2)

    def test_non_admin_reports_failure_without_touching_riin(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / 'result.json'
            with patch('automatic_print.automation.api.riin.__main__.is_administrator', return_value=False), \
                 patch('automatic_print.automation.api.riin.__main__.probe_riin') as probe:
                self.assertEqual(main(['inspect', '--report', str(report)]), 1)
                probe.assert_not_called()
            self.assertFalse(json.loads(report.read_text(encoding='utf-8'))['ok'])

    def test_elevation_forwards_only_the_requested_operation_and_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / 'result.json'
            with patch('automatic_print.automation.api.riin.__main__.is_administrator', return_value=False), \
                 patch('automatic_print.automation.api.riin.__main__.launch_elevated') as launch:
                self.assertEqual(main(['import', '--source', folder, '--report', str(report), '--elevate']), 0)
            launch.assert_called_once_with([
                'import', '--report', str(report.resolve()), '--source', str(Path(folder).resolve()),
            ])

    def test_complete_workflow_runs_all_chunks_and_requires_finished_prn(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            paths = [source / 'a.png', source / 'b.png']
            output = source / 'batch.prn'
            calls = []
            with patch(
                'automatic_print.automation.api.riin.desktop_controls.desktop.png_import_paths',
                return_value=(paths, 'selection'),
            ), patch(
                'automatic_print.automation.api.riin.desktop_controls.desktop.import_chunks',
                return_value=[[paths[0]], [paths[1]]],
            ), patch(
                'automatic_print.automation.api.riin.desktop_controls.desktop.open_import',
                side_effect=lambda handle: calls.append(('open', handle)),
            ), patch(
                'automatic_print.automation.api.riin.desktop_controls.desktop.submit_import_paths',
                side_effect=lambda pid, files, index: {'state': 'submitted', 'chunk': index},
            ), patch(
                'automatic_print.automation.api.riin.workflow.confirm_import',
                side_effect=lambda pid, progress: {'state': 'confirmed'},
            ), patch(
                'automatic_print.automation.api.riin.desktop_controls.desktop.open_output',
                return_value={'state': 'output_opened'},
            ), patch(
                'automatic_print.automation.api.riin.output.new_document',
                return_value={'state': 'new_document', 'title': '未命名-12'},
            ), patch(
                'automatic_print.automation.api.riin.desktop_controls.desktop.select_document',
                side_effect=lambda handle, title: calls.append(('select', handle, title))
                or {'state': 'document_selected'},
            ), patch(
                'automatic_print.automation.api.riin.output.begin_file_output',
                return_value={'state': 'file_mode'},
            ), patch(
                'automatic_print.automation.api.riin.output.save_print_file',
                return_value={'state': 'save_requested'},
            ), patch(
                'automatic_print.automation.api.riin.output.wait_for_print_file',
                return_value={'state': 'prn_generated', 'bytes': 123},
            ), patch(
                'automatic_print.automation.api.riin.output.load_printexp',
                return_value={'state': 'printexp_loaded'},
            ):
                result = automate_layout_to_prn(10, 20, source, output)
            self.assertEqual(calls, [
                ('open', 10), ('open', 10),
                ('select', 10, '未命名-12'),
            ])
            self.assertEqual(result['state'], 'completed')
            self.assertEqual(result['image_count'], 2)
            self.assertEqual(result['chunk_count'], 2)
            self.assertEqual(result['bytes'], 123)
            self.assertTrue(result['riin_complete'])
            self.assertEqual(result['steps'][-1]['state'], 'printexp_loaded')
