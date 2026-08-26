from fastapi import APIRouter

from app.schemas.ads import LandingPageAuditRequest
from app.services.ai_service import audit_landing_page

router = APIRouter()


@router.post("/landing-page")
async def landing_page_audit(payload: LandingPageAuditRequest):
    return audit_landing_page(payload)
