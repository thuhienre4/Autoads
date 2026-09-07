import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from fastapi import HTTPException
from app.services import account_diagnostics as diagnostics


class AccountDiagnosticsTests(unittest.TestCase):
    def sync(self, status="ENABLED"):
        return {"accounts": [{"customer_id": "5543582094", "label": "Example", "status": status}], "source": "mcc_live", "synced_at": "2026-09-07T00:00:00+00:00", "error": None}

    def test_pause_does_not_imply_account_suspension(self):
        campaign = NS(id=1, name="Paused campaign", status=NS(name="PAUSED"), primary_status=NS(name="PAUSED"), primary_status_reasons=[])
        service = NS(search=lambda **kw: [NS(campaign=campaign)])
        with patch.object(diagnostics, "discover_mcc_customer_accounts", return_value=self.sync()), patch.object(diagnostics, "build_google_ads_client", return_value=NS(get_service=lambda _: service)):
            report = diagnostics.diagnose_account("5543582094")
        self.assertEqual(report["status"], "ENABLED")
        self.assertEqual(report["campaigns"][0]["reasons"][0]["code"], "CAMPAIGN_PAUSED")
        self.assertTrue(report["campaigns_checked"])

    def test_suspended_account_survives_failed_campaign_read_without_guessing_cause(self):
        with patch.object(diagnostics, "discover_mcc_customer_accounts", return_value=self.sync("SUSPENDED")), patch.object(diagnostics, "build_google_ads_client", side_effect=RuntimeError("private internal detail")):
            report = diagnostics.diagnose_account("5543582094")
        self.assertEqual(report["status"], "SUSPENDED")
        self.assertFalse(report["campaigns_checked"])
        self.assertIn("không cho biết", report["action"])
        self.assertNotIn("private internal detail", str(report))

    def test_unknown_account_never_queries_client(self):
        with patch.object(diagnostics, "discover_mcc_customer_accounts", return_value=self.sync()), patch.object(diagnostics, "build_google_ads_client") as client:
            with self.assertRaises(HTTPException):
                diagnostics.diagnose_account("0000000000")
            client.assert_not_called()

    def test_unknown_reason_is_preserved_and_campaign_limit_is_explicit(self):
        campaign = NS(id=1, name="Example", status=NS(name="ENABLED"), primary_status=NS(name="LIMITED"), primary_status_reasons=[NS(name="FUTURE_REASON")])
        service = NS(search=lambda **kw: [NS(campaign=campaign)] * 101)
        with patch.object(diagnostics, "discover_mcc_customer_accounts", return_value=self.sync()), patch.object(diagnostics, "build_google_ads_client", return_value=NS(get_service=lambda _: service)):
            report = diagnostics.diagnose_account("5543582094")
        self.assertTrue(report["truncated"])
        self.assertEqual(len(report["campaigns"]), 100)
        self.assertEqual(report["campaigns"][0]["reasons"][0]["code"], "FUTURE_REASON")


if __name__ == "__main__":
    unittest.main()
