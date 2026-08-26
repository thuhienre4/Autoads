from fastapi import APIRouter

from app.schemas.ads import AdGenerationRequest, AngleFinderRequest, LandingPageAuditRequest, SearchCampaignOptimizationRequest
from app.services.ai_service import (
    audit_landing_page,
    find_ad_angles,
    generate_google_ads_copy,
    generate_search_campaign_optimization,
)

router = APIRouter()


@router.post("/generate-ads")
def generate_ads(payload: AdGenerationRequest):
    # A sync route runs in FastAPI's worker pool, which lets the optional
    # Playwright sync client render JavaScript without blocking the event loop.
    return generate_google_ads_copy(payload)


@router.post("/landing-page-analyzer")
async def landing_page_analyzer(payload: LandingPageAuditRequest):
    return audit_landing_page(payload)


@router.post("/angle-finder")
async def angle_finder(payload: AngleFinderRequest):
    return find_ad_angles(payload.niche_or_product, payload.target_audience)


@router.post("/search-campaign-optimizer")
async def search_campaign_optimizer(payload: SearchCampaignOptimizationRequest):
    return generate_search_campaign_optimization(payload)
