import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.services import publish_history_service as history
from app.core.config import settings


class HistoryStorageTests(unittest.TestCase):
    def test_volume_survives_module_reload(self):
        try:
            with tempfile.TemporaryDirectory() as directory:
                with patch.object(settings, 'RAILWAY_VOLUME_MOUNT_PATH', directory):
                    importlib.reload(history)
                    self.assertEqual(history.HISTORY_FILE, Path(directory) / 'publish_history.json')
                    history._write_history([{'id': 'retained'}])
                    importlib.reload(history)
                    self.assertEqual(history.list_publish_history(), [{'id': 'retained'}])
        finally:
            importlib.reload(history)

    def test_migration_preserves_existing_volume_and_legacy_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / 'legacy.json'
            legacy.write_text(json.dumps([{'id': 'old'}]), encoding='utf-8')
            volume = root / 'volume'
            with patch.object(history, 'DATA_DIR', volume), patch.object(history, 'HISTORY_FILE', volume / 'publish_history.json'), patch.object(history, 'LEGACY_HISTORY_FILE', legacy):
                self.assertEqual(history._read_history(), [{'id': 'old'}])
                history._write_history([{'id': 'new'}])
                self.assertEqual(history._read_history(), [{'id': 'new'}])
                self.assertEqual(json.loads(legacy.read_text()), [{'id': 'old'}])
                self.assertEqual(list(volume.glob('*.tmp')), [])
