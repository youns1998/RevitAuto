"""Check cancellation and transaction flow with a stand-in API, not real Revit."""
import importlib
import json
import os
import sys
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

from revitauto.sheets import SheetSpec
from revitauto.reports import ExportCancelled, new_snapshot

with patch.dict(sys.modules, {'pyrevit': SimpleNamespace(DB=None, forms=None, revit=None, script=None)}):
    commands = importlib.import_module('revitauto.commands')


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.transaction = Mock()
        self.transaction.Start.return_value = 'started'
        self.transaction.GetStatus.return_value = 'started'
        self.transaction.Commit.return_value = 'committed'
        self.db = SimpleNamespace(
            Transaction=Mock(return_value=self.transaction),
            TransactionStatus=SimpleNamespace(Started='started', Committed='committed'))
        self.patch = patch.object(commands, 'DB', self.db)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_success_commits_once(self):
        work = Mock()
        commands._change('document', 'batch', work)
        work.assert_called_once_with()
        self.transaction.Commit.assert_called_once_with()
        self.transaction.RollBack.assert_not_called()
        self.transaction.Dispose.assert_called_once_with()

    def test_error_rolls_back_all_changes(self):
        with self.assertRaises(ValueError):
            commands._change('document', 'batch', Mock(side_effect=ValueError('invalid view')))
        self.transaction.RollBack.assert_called_once_with()
        self.transaction.Commit.assert_not_called()
        self.transaction.Dispose.assert_called_once_with()

    def test_failed_start_never_changes_model(self):
        self.transaction.Start.return_value = 'not-started'
        self.transaction.GetStatus.return_value = 'not-started'
        work = Mock()
        with self.assertRaises(RuntimeError):
            commands._change('document', 'batch', work)
        work.assert_not_called()
        self.transaction.Commit.assert_not_called()
        self.transaction.RollBack.assert_not_called()

    def test_revit_rejected_commit_is_failure(self):
        self.transaction.Commit.return_value = 'rolledback'
        self.transaction.GetStatus.return_value = 'rolledback'
        with self.assertRaises(RuntimeError):
            commands._change('document', 'batch', Mock())
        self.transaction.RollBack.assert_not_called()
        self.transaction.Dispose.assert_called_once_with()


class NameValidationTests(unittest.TestCase):
    def test_invalid_name_is_rejected_before_model_changes(self):
        naming = Mock()
        naming.IsValidName.return_value = False
        with patch.object(commands, 'DB', SimpleNamespace(NamingUtils=naming)):
            with self.assertRaises(ValueError):
                commands._validate_revit_names([SheetSpec('A101', '{3D}')])

    def test_korean_name_passes_api_validation(self):
        naming = Mock()
        naming.IsValidName.return_value = True
        with patch.object(commands, 'DB', SimpleNamespace(NamingUtils=naming)):
            commands._validate_revit_names([SheetSpec('A101', '1층 평면도')])
        naming.IsValidName.assert_called_once_with('1층 평면도')


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.forms = Mock()
        self.change = Mock()
        for name, replacement in (('forms', self.forms), ('_change', self.change), ('_validate_revit_names', Mock())):
            active = patch.object(commands, name, replacement)
            active.start()
            self.addCleanup(active.stop)

    def test_file_cancel_does_not_start_transaction(self):
        self.forms.pick_file.return_value = None
        commands.import_sheets('document')
        self.change.assert_not_called()

    def test_collision_stops_before_titleblock_or_transaction(self):
        with patch.object(commands, 'read_csv_file', return_value=[SheetSpec('A101', 'plan')]), \
             patch.object(commands, '_sheets', return_value=[SimpleNamespace(SheetNumber='a101')]), \
             patch.object(commands, '_titleblock') as titleblock:
            with self.assertRaises(ValueError):
                commands.import_sheets('document')
            titleblock.assert_not_called()
            self.change.assert_not_called()

    def test_preview_cancel_does_not_start_transaction(self):
        with patch.object(commands, 'read_csv_file', return_value=[SheetSpec('A101', 'plan')]), \
             patch.object(commands, '_sheets', return_value=[]), \
             patch.object(commands, '_titleblock', return_value='block'), \
             patch.object(commands, '_confirm', return_value=False):
            commands.import_sheets('document')
            self.change.assert_not_called()

    def test_titleblock_cancel_does_not_start_transaction(self):
        with patch.object(commands, 'read_csv_file', return_value=[SheetSpec('A101', 'plan')]), \
             patch.object(commands, '_sheets', return_value=[]), \
             patch.object(commands, '_titleblock', return_value=None), \
             patch.object(commands, '_confirm') as confirm:
            commands.import_sheets('document')
            confirm.assert_not_called()
            self.change.assert_not_called()


class ExportCommandTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = os.path.join(self.temporary.name, 'details.zip')
        self.forms = Mock()
        self.forms.SelectFromList.show.return_value = ['A101 · 평면도']
        self.forms.CommandSwitchWindow.show.return_value = 'CSV·JSON 상세정보'
        self.forms.save_file.return_value = self.path
        progress = Mock(cancelled=False)
        self.forms.ProgressBar.return_value.__enter__ = Mock(return_value=progress)
        self.forms.ProgressBar.return_value.__exit__ = Mock(return_value=False)
        self.snapshot = new_snapshot('실습')
        self.snapshot['sheets'].append({'key': 'host:1', 'number': 'A101', 'name': '평면도'})
        self.collector = Mock()
        self.collector.snapshot.return_value = self.snapshot
        self.collector.issue.side_effect = lambda scope, entity, field, error: self.snapshot['issues'].append(
            {'scope': scope, 'entity': entity, 'field': field, 'message': str(error)})
        module_patch = patch.dict(sys.modules, {'pyrevit': SimpleNamespace(DB=None)})
        module_patch.start()
        self.addCleanup(module_patch.stop)
        self.adapter = importlib.import_module('revitauto.revit_report')
        for target, name, value in ((commands, 'forms', self.forms),
                                    (commands, '_sheets', Mock(return_value=[SimpleNamespace(SheetNumber='A101', Name='평면도')])),
                                    (self.adapter, 'SnapshotCollector', Mock(return_value=self.collector))):
            active = patch.object(target, name, value)
            active.start()
            self.addCleanup(active.stop)

    def test_cancel_selection_never_writes(self):
        self.forms.SelectFromList.show.return_value = None
        commands.export_sheets('document')
        self.forms.save_file.assert_not_called()
        self.collector.snapshot.assert_not_called()

    def test_csv_json_export_writes_bundle(self):
        commands.export_sheets('document')
        with zipfile.ZipFile(self.path) as archive:
            self.assertIn('parameters.csv', archive.namelist())
            self.assertEqual(json.loads(archive.read('manifest.json'))['pdf'], 'not_requested')
        self.assertEqual(os.listdir(self.temporary.name), ['details.zip'])

    def test_cancel_collection_does_not_publish(self):
        self.collector.snapshot.side_effect = ExportCancelled()
        commands.export_sheets('document')
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(os.listdir(self.temporary.name), [])

    def test_pdf_failure_keeps_metadata_and_reports_issue(self):
        self.forms.CommandSwitchWindow.show.return_value = 'CSV·JSON 상세정보 + 시트 PDF'
        with patch.object(self.adapter, 'export_pdf', side_effect=ValueError('cannot print')):
            commands.export_sheets('document')
        with zipfile.ZipFile(self.path) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual(manifest['pdf'], 'failed_see_issues')
            self.assertEqual(manifest['counts']['issues'], 1)
            self.assertNotIn('sheets.pdf', archive.namelist())
