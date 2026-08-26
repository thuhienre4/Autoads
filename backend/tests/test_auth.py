import unittest
from urllib.parse import parse_qs, urlparse

from app.api.routes.auth import GOOGLE_ADS_SCOPES, _build_google_auth_url


class GoogleOAuthUrlTests(unittest.TestCase):
    def test_google_ads_auth_url_starts_fresh_consent_flow(self):
        params = parse_qs(urlparse(_build_google_auth_url(GOOGLE_ADS_SCOPES, "test-state")).query)

        self.assertEqual(["select_account consent"], params["prompt"])
        self.assertEqual(["offline"], params["access_type"])
        self.assertNotIn("include_granted_scopes", params)


if __name__ == "__main__":
    unittest.main()
