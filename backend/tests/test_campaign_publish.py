import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.api.routes.google_ads import (
    CampaignPublishRequest,
    _campaign_payload_from_history,
    _validate_google_ads_payload,
    publish_campaign,
)


class CampaignPublishStatusTests(unittest.IsolatedAsyncioTestCase):
    def payload(self, enable_immediately: bool | None) -> CampaignPublishRequest:
        values = dict(
            campaign_name="Search Campaign Test",
            ad_group_name="WordPress Plugins - Exact",
            daily_budget_vnd=300000,
            manual_cpc_bid_vnd=5000,
            landing_page_url="https://example.com/landing",
            keywords=["wordpress plugin", "woocommerce plugin"],
            headlines=["WordPress Plugin", "WooCommerce Tools", "Get Started Today"],
            descriptions=[
                "Explore WordPress tools built for WooCommerce stores.",
                "Get expert support and start improving your store today.",
            ],
            customer_ids=["4774051692"],
            dry_run=True,
        )
        if enable_immediately is not None:
            values["enable_immediately"] = enable_immediately
        return CampaignPublishRequest(**values)

    async def test_dry_run_plans_enabled_delivery_when_selected(self):
        with (
            patch(
                "app.api.routes.google_ads.account_status",
                new=AsyncMock(return_value={"can_publish_live": True}),
            ),
            patch("app.api.routes.google_ads.record_publish_history", return_value={"id": "test"}),
        ):
            result = await publish_campaign(self.payload(enable_immediately=True))

        self.assertEqual("ENABLED", result["plan"]["campaign"]["status"])
        self.assertEqual("ENABLED", result["plan"]["responsive_search_ad"]["status"])
        self.assertEqual("WordPress Plugins - Exact", result["plan"]["ad_group"]["name"])
        self.assertTrue(result["plan"]["campaign"]["networks"]["google_search"])
        self.assertFalse(result["plan"]["campaign"]["networks"]["display_network"])
        self.assertEqual("dry_run", result["mode"])

    async def test_explicit_paused_delivery_is_still_supported(self):
        with (
            patch(
                "app.api.routes.google_ads.account_status",
                new=AsyncMock(return_value={"can_publish_live": True}),
            ),
            patch("app.api.routes.google_ads.record_publish_history", return_value={"id": "test"}),
        ):
            result = await publish_campaign(self.payload(enable_immediately=False))

        self.assertEqual("PAUSED", result["plan"]["campaign"]["status"])
        self.assertEqual("PAUSED", result["plan"]["responsive_search_ad"]["status"])

    async def test_publish_defaults_to_enabled_delivery(self):
        with (
            patch(
                "app.api.routes.google_ads.account_status",
                new=AsyncMock(return_value={"can_publish_live": True}),
            ),
            patch("app.api.routes.google_ads.record_publish_history", return_value={"id": "test"}),
        ):
            result = await publish_campaign(self.payload(enable_immediately=None))

        self.assertEqual("ENABLED", result["plan"]["campaign"]["status"])
        self.assertEqual("ENABLED", result["plan"]["responsive_search_ad"]["status"])

    def test_scheduled_history_preserves_enable_choice(self):
        payload = _campaign_payload_from_history(
            {
                "campaign_name": "Scheduled Campaign",
                "landing_page_url": "https://example.com/landing",
                "customer_ids": ["4774051692"],
                "enable_immediately": True,
                "budget": {"daily_budget_vnd": 300000, "manual_cpc_bid_vnd": 5000},
                "content": {
                    "keywords": ["wordpress plugin"],
                    "headlines": ["WordPress Plugin", "WooCommerce Tools", "Get Started Today"],
                    "descriptions": ["Explore WordPress tools.", "Get expert support today."],
                },
                "plan": {"campaign": {"status": "ENABLED"}},
            }
        )

        self.assertTrue(payload.enable_immediately)

    def test_usd_budget_accepts_cents_and_uses_usd_validation_limits(self):
        payload = self.payload(enable_immediately=True).model_copy(
            update={
                "daily_budget_vnd": Decimal("15.50"),
                "manual_cpc_bid_vnd": Decimal("0.25"),
                "currency_code": "USD",
            }
        )

        self.assertEqual([], _validate_google_ads_payload(payload))

    async def test_rejects_currency_that_does_not_match_selected_account(self):
        payload = self.payload(enable_immediately=True).model_copy(
            update={
                "daily_budget_vnd": Decimal("15"),
                "manual_cpc_bid_vnd": Decimal("0.25"),
                "currency_code": "USD",
            }
        )
        status = {
            "can_publish_live": True,
            "accounts": [{"customer_id": "4774051692", "currency_code": "VND"}],
        }
        with patch(
            "app.api.routes.google_ads.account_status",
            new=AsyncMock(return_value=status),
        ):
            with self.assertRaises(HTTPException) as raised:
                await publish_campaign(payload)

        self.assertEqual(422, raised.exception.status_code)
        self.assertIn("4774051692 (VND)", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
