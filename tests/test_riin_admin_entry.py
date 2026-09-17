"""Contracts for the bounded, user-elevated RIIN entry point."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from automatic_print.automation.api.riin.__main__ import main
from automatic_print.automation.api.riin.desktop import png_import_paths


class AdminEntryTests(unittest.TestCase):
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
