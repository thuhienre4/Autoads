"""
Main FastAPI application for AI Google Ads Optimizer
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
import asyncio
import logging

from app.api.routes import auth, campaigns, keywords, recommendations, ai, audit, predictions, google_ads, affiliate, automation, search
from app.core.config import settings
from app.services.affiliate_link_service import record_click
from app.services.google_ads_data_service import clean_customer_id, configured_customer_ids
from app.utils.database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
scheduled_worker_task = None

# Create FastAPI app
app = FastAPI(
    title="AI Google Ads Optimizer API",
    description="Advanced AI-powered Google Ads optimization platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
@app.on_event("startup")
async def startup():
    """Initialize database on startup"""
    global scheduled_worker_task
    customer_ids = configured_customer_ids()
    logger.info("LAN frontend URL: %s", settings.FRONTEND_URL)
    logger.info("LAN backend URL: http://%s:%s", "10.29.56.188", settings.PORT)
    logger.info("Google Ads login customer ID: %s", clean_customer_id(settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID) or "not configured")
    logger.info(
        "Google Ads customer account IDs from config/data file: %s",
        ", ".join(customer_ids) if customer_ids else "none",
    )
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
    if scheduled_worker_task is None:
        scheduled_worker_task = asyncio.create_task(scheduled_publish_worker())


async def scheduled_publish_worker():
    """Poll local scheduled publish history and publish due PAUSED campaigns."""
    while True:
        try:
            result = await google_ads.run_due_scheduled_campaigns(dry_run=False, limit=10)
            if result.get("due"):
                logger.info("Scheduled publish worker result: %s", result)
        except Exception as exc:
            logger.error("Scheduled publish worker error: %s", exc)
        await asyncio.sleep(60)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "AI Google Ads Optimizer API",
        "version": "1.0.0"
    }

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(campaigns.router, prefix="/api/v1/campaigns", tags=["Campaigns"])
app.include_router(keywords.router, prefix="/api/v1/keywords", tags=["Keywords"])
app.include_router(recommendations.router, prefix="/api/v1/recommendations", tags=["Recommendations"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["Audit"])
app.include_router(predictions.router, prefix="/api/v1/predictions", tags=["Predictions"])
app.include_router(google_ads.router, prefix="/api/v1/google-ads", tags=["Google Ads"])
app.include_router(affiliate.router, prefix="/api/v1/affiliate", tags=["Affiliate Links"])
app.include_router(automation.router, prefix="/api/v1/automation", tags=["Automation"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])


@app.get("/go/{code}")
async def affiliate_clean_redirect(code: str, request: Request):
    link = record_click(
        code,
        user_agent=request.headers.get("user-agent"),
        referer=request.headers.get("referer"),
        ip=request.client.host if request.client else None,
    )
    if not link:
        return JSONResponse(status_code=404, content={"detail": "Short affiliate link not found."})
    return RedirectResponse(url=link["affiliate_url"], status_code=302)

# Error handlers
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to AI Google Ads Optimizer API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
