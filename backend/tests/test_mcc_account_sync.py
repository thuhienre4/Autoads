import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import google_ads_data_service as service


def customer_row(
    customer_id: str,
    name: str,
    *,
    manager: bool = False,
    level: int = 1,
    status: str = "ENABLED",
):
    return SimpleNamespace(
        customer_client=SimpleNamespace(
            client_customer=f"customers/{customer_id}",
            descriptive_name=name,
            currency_code="VND",
            time_zone="Asia/Ho_Chi_Minh",
            manager=manager,
            level=level,
            status=SimpleNamespace(name=status),
            test_account=False,
        )
    )


class MccAccountSyncTests(unittest.TestCase):
    def test_discovers_each_client_status_and_excludes_managers(self):
        rows = [
            customer_row("1112223333", "Accepted Client"),
            customer_row("4445556666", "Sub Manager", manager=True),
            customer_row("7778889999", "Cancelled Client", status="CANCELED"),
        ]
        google_ads_service = SimpleNamespace(search=lambda **_: rows)
        client = SimpleNamespace(get_service=lambda _: google_ads_service)

        with (
            patch.object(service.settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "123-456-7890"),
            patch.object(service.settings, "GOOGLE_ADS_DEVELOPER_TOKEN", "developer-token"),
            patch.object(service, "configured_customer_ids", return_value=[]),
            patch.object(service, "build_google_ads_client", return_value=client),
            patch.dict(
                service.oauth_session,
                {
                    "token": {"refresh_token": "refresh-token"},
                    "scopes": "openid https://www.googleapis.com/auth/adwords",
                },
            ),
        ):
            result = service.discover_mcc_customer_accounts(force=True)

        self.assertEqual("mcc_live", result["source"])
        self.assertEqual(
            ["1112223333", "7778889999"],
            [item["customer_id"] for item in result["accounts"]],
        )
        self.assertEqual("Accepted Client", result["accounts"][0]["label"])
        self.assertEqual("ENABLED", result["accounts"][0]["status"])
        self.assertTrue(result["accounts"][0]["publish_eligible"])
        self.assertEqual("CANCELED", result["accounts"][1]["status"])
        self.assertFalse(result["accounts"][1]["publish_eligible"])

    def test_keeps_configured_accounts_as_safe_fallback(self):
        google_ads_service = SimpleNamespace(search=lambda **_: [])
        client = SimpleNamespace(get_service=lambda _: google_ads_service)

        with (
            patch.object(service.settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "1234567890"),
            patch.object(service.settings, "GOOGLE_ADS_DEVELOPER_TOKEN", "developer-token"),
            patch.object(service, "configured_customer_ids", return_value=["9990001112"]),
            patch.object(service, "build_google_ads_client", return_value=client),
            patch.dict(
                service.oauth_session,
                {
                    "token": {"refresh_token": "refresh-token"},
                    "scopes": "https://www.googleapis.com/auth/adwords",
                },
            ),
        ):
            result = service.discover_mcc_customer_accounts(force=True)

        self.assertEqual(["9990001112"], [item["customer_id"] for item in result["accounts"]])
        self.assertEqual("configuration", result["accounts"][0]["source"])
        self.assertFalse(result["accounts"][0]["publish_eligible"])

    def test_available_customer_ids_uses_live_mcc_accounts(self):
        with (
            patch.object(
                service,
                "discover_mcc_customer_accounts",
                return_value={
                    "accounts": [
                        {"customer_id": "111-222-3333", "publish_eligible": True},
                        {"customer_id": "4445556666", "publish_eligible": False},
                    ]
                },
            ),
            patch.object(service, "configured_customer_ids", return_value=["9990001112"]),
        ):
            result = service.available_customer_ids()

        self.assertEqual(["1112223333"], result)


if __name__ == "__main__":
    unittest.main()
