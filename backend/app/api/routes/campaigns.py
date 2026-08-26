from fastapi import APIRouter, Query

from app.services.analysis import dashboard_summary
from app.services.sample_data import CAMPAIGNS, daily_metrics

router = APIRouter()


@router.get("")
async def list_campaigns():
    return CAMPAIGNS


@router.post("/sync")
async def sync_campaigns():
    return {
        "status": "completed",
        "records_synced": {
            "campaigns": 3,
            "ad_groups": 8,
            "keywords": 128,
            "search_terms": 540,
        },
        "source": "demo-google-ads-sync",
    }


@router.get("/dashboard")
async def dashboard(days: int = Query(default=30, ge=1, le=365)):
    return {"summary": dashboard_summary(days), "daily": daily_metrics(days), "campaigns": CAMPAIGNS}
