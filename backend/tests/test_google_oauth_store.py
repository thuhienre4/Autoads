import tempfile
import unittest
from pathlib import Path

from app.services.google_oauth_store import DEFAULT_STORE_PATH, resolve_store_path


class GoogleOAuthStoreTests(unittest.TestCase):
    def test_explicit_store_path_has_priority(self):
        self.assertEqual(
            Path("/custom/session.json"),
            resolve_store_path("/custom/session.json", "/data"),
        )

    def test_railway_volume_gets_session_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                Path(directory) / "google_oauth_session.json",
                resolve_store_path(None, directory),
            )

    def test_local_path_is_the_fallback(self):
        self.assertEqual(DEFAULT_STORE_PATH, resolve_store_path())


if __name__ == "__main__":
    unittest.main()
