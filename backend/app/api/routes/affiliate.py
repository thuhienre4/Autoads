from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel, HttpUrl

from app.services.affiliate_research_service import (
    affiliate_research_report_to_csv,
    list_affiliate_research_reports,
    research_affiliate_projects,
)
from app.services.affiliate_link_service import (
    build_affiliate_link,
    get_link_stats,
    load_affiliate_config,
    record_click,
    scan_affiliate_projects,
    search_affiliate_projects_by_name,
)
from app.services.google_ads_data_service import fetch_google_ads_landing_page_projects

router = APIRouter()


class AffiliateWrapRequest(BaseModel):
    url: HttpUrl
    use_redirect_tracking: bool = True
    shorten: bool = True
    sub_id: str | None = None
    campaign: str | None = None
    public_base_url: str | None = None


class AffiliateProject(BaseModel):
    name: str | None = None
    url: HttpUrl
    source: str | None = None
    customer_ids: list[str] = []


class AffiliateProjectScanRequest(BaseModel):
    projects: list[AffiliateProject] = []
    include_unmatched: bool = False


class AffiliateResearchRequest(BaseModel):
    project_names: list[str] = []
    max_results: int = 5


@router.get("/programs")
async def affiliate_programs():
    config = load_affiliate_config()
    return {"programs": config.get("programs", [])}


@router.get("/projects/scan")
async def scan_affiliate_projects_from_history(include_unmatched: bool = False):
    return scan_affiliate_projects(include_unmatched=include_unmatched)


@router.get("/projects/search")
async def search_affiliate_projects(project_name: str, include_unmatched: bool = False, limit: int = 25):
    if not project_name.strip():
        raise HTTPException(status_code=400, detail="project_name is required.")
    return search_affiliate_projects_by_name(project_name, include_unmatched=include_unmatched, limit=limit)


@router.post("/projects/scan")
async def scan_affiliate_projects_from_payload(payload: AffiliateProjectScanRequest):
    return scan_affiliate_projects(
        projects=[project.model_dump() for project in payload.projects],
        include_unmatched=payload.include_unmatched,
    )


@router.get("/projects/scan-google-ads")
async def scan_affiliate_projects_from_google_ads(
    include_unmatched: bool = False,
    customer_ids: str | None = None,
    project_name: str | None = None,
    limit_per_account: int = 500,
):
    selected_customer_ids = [
        item.strip()
        for item in (customer_ids or "").split(",")
        if item.strip()
    ] or None
    google_ads_data = fetch_google_ads_landing_page_projects(
        customer_ids=selected_customer_ids,
        limit_per_account=limit_per_account,
        project_name=project_name,
    )
    scan = scan_affiliate_projects(
        projects=google_ads_data["projects"],
        include_unmatched=include_unmatched,
    )
    return {
        **scan,
        "source": google_ads_data["source"],
        "customer_ids": google_ads_data["customer_ids"],
        "project_name": google_ads_data["project_name"],
        "google_ads_project_count": len(google_ads_data["projects"]),
        "google_ads_total_before_filter": google_ads_data["total_projects_before_filter"],
        "google_ads_errors": google_ads_data["errors"],
    }


@router.post("/research")
async def research_affiliate_programs(payload: AffiliateResearchRequest):
    if not payload.project_names:
        raise HTTPException(status_code=400, detail="project_names is required.")
    return await research_affiliate_projects(payload.project_names, max_results=payload.max_results)


@router.get("/research/reports")
async def affiliate_research_reports():
    reports = list_affiliate_research_reports()
    return {
        "items": [
            {
                "id": report.get("id"),
                "created_at": report.get("created_at"),
                "summary": report.get("summary", {}),
            }
            for report in reports
        ]
    }


@router.get("/research/reports/{report_id}/export.csv")
async def export_affiliate_research_report(report_id: str):
    report = next((item for item in list_affiliate_research_reports() if item.get("id") == report_id), None)
    if not report:
        raise HTTPException(status_code=404, detail="Affiliate research report not found.")
    return PlainTextResponse(
        affiliate_research_report_to_csv(report),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="affiliate-research-{report_id}.csv"'},
    )


@router.post("/wrap")
async def wrap_affiliate_link(payload: AffiliateWrapRequest, request: Request):
    base_url = (payload.public_base_url or str(request.base_url)).rstrip("/")
    if base_url.endswith("/api/v1"):
        api_base_url = base_url
    else:
        api_base_url = f"{base_url}/api/v1"
    return build_affiliate_link(
        str(payload.url),
        base_url=api_base_url,
        use_redirect_tracking=payload.use_redirect_tracking,
        shorten=payload.shorten,
        sub_id=payload.sub_id,
        campaign=payload.campaign,
    )


@router.get("/r/{code}")
async def redirect_affiliate_link(code: str, request: Request):
    link = record_click(
        code,
        user_agent=request.headers.get("user-agent"),
        referer=request.headers.get("referer"),
        ip=request.client.host if request.client else None,
    )
    if not link:
        raise HTTPException(status_code=404, detail="Short affiliate link not found.")
    return RedirectResponse(url=link["affiliate_url"], status_code=302)


@router.get("/stats/{code}")
async def affiliate_link_stats(code: str):
    stats = get_link_stats(code)
    if not stats:
        raise HTTPException(status_code=404, detail="Short affiliate link not found.")
    return stats
