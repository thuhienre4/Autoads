from typing import Annotated
from fastapi import APIRouter, UploadFile, File, Body
from starlette.concurrency import run_in_threadpool

from app.schemas.ads import AdGenerationRequest, AngleFinderRequest, LandingPageAuditRequest, SearchCampaignOptimizationRequest
from app.services.ai_service import (
    audit_landing_page,
    find_ad_angles,
    generate_google_ads_copy,
    generate_search_campaign_optimization,
)
from app.services.win_templates import WinTemplateInput, list_templates, save_template, save_templates, delete_template
from app.services.win_template_import import preview_win_file, MAX_FILE_BYTES

router = APIRouter()


@router.post("/win-templates/preview")
async def preview_win_templates(file: UploadFile = File(...)):
    try:
        content = await file.read(MAX_FILE_BYTES + 1)
        return await run_in_threadpool(preview_win_file, content, file.filename or "")
    finally:
        await file.close()


@router.post("/win-templates/batch", status_code=201)
def create_win_templates(payload: Annotated[list[WinTemplateInput], Body(min_length=1, max_length=50)]):
    return {"templates": save_templates(payload)}

@router.get("/win-templates")
def win_templates():
    return {"templates": list_templates()}


@router.post("/win-templates", status_code=201)
def create_win_template(payload: WinTemplateInput):
    return save_template(payload)


@router.delete("/win-templates/{template_id}")
def remove_win_template(template_id: str):
    return delete_template(template_id)


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
def search_campaign_optimizer(payload: SearchCampaignOptimizationRequest):
    return generate_search_campaign_optimization(payload)
