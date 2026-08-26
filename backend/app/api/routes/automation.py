from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, HttpUrl

from app.api.routes.google_ads import CampaignPublishRequest, publish_campaign
from app.schemas.ads import AdGenerationRequest
from app.services.ai_service import generate_google_ads_copy

router = APIRouter()


class DailyAutomationRequest(BaseModel):
    workflow_name: str = Field(default="Daily Search Ads Automation", min_length=3)
    product_name: str = Field(min_length=2)
    landing_page_url: HttpUrl
    target_keywords: list[str] = Field(default_factory=list)
    customer_ids: list[str] = Field(default_factory=list)
    language: str = "English"
    target_audience: str | None = None
    landing_page_message: str | None = None
    primary_offer: str | None = None
    primary_cta: str | None = None
    trust_signals: str | None = None
    daily_budget_vnd: Decimal = Field(default=300000, gt=0)
    manual_cpc_bid_vnd: Decimal = Field(default=5000, gt=0)
    currency_code: Literal["VND", "USD"] = "VND"
    target_location: str = "Vietnam"
    excluded_locations: list[str] = Field(default_factory=list)
    excluded_location_ids: list[int] = Field(default_factory=list)
    schedule_enabled: bool = False
    scheduled_at: str | None = None
    schedule_timezone: str = "Asia/Saigon"
    dry_run: bool = True


@router.post("/daily-run")
async def daily_run(payload: DailyAutomationRequest):
    ad_request = AdGenerationRequest(
        product_name=payload.product_name,
        website=payload.landing_page_url,
        landing_page_url=payload.landing_page_url,
        language=payload.language,
        target_audience=payload.target_audience,
        landing_page_message=payload.landing_page_message,
        primary_offer=payload.primary_offer,
        primary_cta=payload.primary_cta,
        trust_signals=payload.trust_signals,
        target_keywords=payload.target_keywords,
    )
    generated = generate_google_ads_copy(ad_request)
    keywords = payload.target_keywords or generated.get("landing_page_alignment", {}).get("keywords_used", [])
    campaign_name = f"{payload.workflow_name} - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    campaign_payload = CampaignPublishRequest(
        campaign_name=campaign_name,
        daily_budget_vnd=payload.daily_budget_vnd,
        manual_cpc_bid_vnd=payload.manual_cpc_bid_vnd,
        currency_code=payload.currency_code,
        landing_page_url=payload.landing_page_url,
        target_location=payload.target_location,
        excluded_locations=payload.excluded_locations,
        excluded_location_ids=payload.excluded_location_ids,
        keywords=keywords,
        headlines=generated.get("headlines", [])[:15],
        descriptions=generated.get("descriptions", [])[:4],
        customer_ids=payload.customer_ids,
        schedule_enabled=payload.schedule_enabled,
        scheduled_at=payload.scheduled_at,
        schedule_timezone=payload.schedule_timezone,
        dry_run=payload.dry_run,
    )
    publish_result = await publish_campaign(campaign_payload)
    return {
        "workflow": {
            "name": payload.workflow_name,
            "steps": [
                "read_landing_page",
                "generate_rsa_content",
                "select_keywords",
                "validate_or_publish_paused_campaign",
                "store_history_for_measurement",
            ],
            "safe_mode": payload.dry_run or payload.schedule_enabled,
        },
        "generated_ads": generated,
        "publish_result": publish_result,
    }
