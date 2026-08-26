from datetime import date
from typing import Any
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class MetricSummary(BaseModel):
    clicks: int
    impressions: int
    cost: float
    conversions: float
    conversion_rate: float
    roas: float
    avg_cpc: float
    avg_ctr: float


class DailyMetric(BaseModel):
    date: date
    clicks: int
    impressions: int
    cost: float
    conversions: float
    conversion_value: float
    roas: float


class Campaign(BaseModel):
    id: int
    name: str
    status: str
    budget_amount: float
    clicks: int
    impressions: int
    cost: float
    conversions: float
    conversion_value: float
    roas: float


class KeywordInsight(BaseModel):
    id: int
    keyword_text: str
    match_type: str
    cost: float
    clicks: int
    conversions: float
    ctr: float
    cpc: float
    roas: float
    label: str
    recommendations: list[str]
    priority: Literal["low", "medium", "high"]


class SearchTermInsight(BaseModel):
    search_term: str
    intent: str
    clicks: int
    cost: float
    conversions: float
    action: str
    reason: str


class AdGenerationRequest(BaseModel):
    product_name: str | None = None
    website: HttpUrl
    landing_page_url: HttpUrl
    language: str = "English"
    tone: str = "Professional"
    target_audience: str | None = None
    landing_page_message: str | None = None
    primary_offer: str | None = None
    primary_cta: str | None = None
    trust_signals: str | None = None
    target_keywords: list[str] = []


class AdGenerationResponse(BaseModel):
    headlines: list[str]
    descriptions: list[str]
    cta_suggestions: list[str]
    seo_analysis: dict[str, Any] = {}


class LandingPageAuditRequest(BaseModel):
    url: HttpUrl


class LandingPageAuditResponse(BaseModel):
    url: HttpUrl
    seo_score: int
    ux_score: int
    conversion_score: int
    mobile_score: int
    findings: list[str]
    recommendations: list[str]


class ConversionPredictionRequest(BaseModel):
    ctr: float
    cpc: float
    device: str
    audience: str
    hour: int = Field(ge=0, le=23)
    day: int = Field(ge=0, le=6)


class ConversionPredictionResponse(BaseModel):
    conversion_probability: float
    recommendation: str
    rationale: str


class AngleFinderRequest(BaseModel):
    niche_or_product: str = Field(min_length=2)
    target_audience: str = Field(min_length=2)


class SearchCampaignOptimizationRequest(BaseModel):
    campaign_name: str | None = None
    product_name: str = "Google Ads Search Campaign"
    landing_page_url: HttpUrl | None = None
    target_audience: str | None = None
    target_keywords: list[str] = []
    campaigns: list[dict[str, Any]] = []
    ad_groups: list[dict[str, Any]] = []
    keywords: list[dict[str, Any]] = []
    search_terms: list[dict[str, Any]] = []
    daily_performance: list[dict[str, Any]] = []
    language: str = "English"


class AdAngle(BaseModel):
    angle: str
    hook: str
    sample_headline: str
    sample_description: str


class Recommendation(BaseModel):
    id: int
    type: str
    title: str
    description: str
    priority: str
    estimated_impact: str
    status: str
