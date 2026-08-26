# API Endpoints

Base URL: `http://localhost:8000/api/v1`

## Authentication

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/auth/google/login` | Start Google OAuth login flow or demo login metadata |
| GET | `/auth/google/callback` | OAuth callback handler placeholder |
| GET | `/auth/me` | Current user profile |

## Google Ads Data

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/campaigns/sync` | Sync campaigns, ad groups, keywords and search terms |
| GET | `/campaigns` | Campaign list |
| GET | `/campaigns/dashboard?days=30` | Dashboard summary and daily trend data |
| GET | `/keywords` | Keyword performance |
| GET | `/keywords/waste` | Keywords labelled `Dang dot ngan sach` |
| GET | `/keywords/growth` | Keywords labelled `Keyword tang truong` |
| GET | `/keywords/search-terms` | New keyword and negative keyword suggestions |

## AI Optimization

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/recommendations` | Consolidated optimization actions |
| GET | `/recommendations/daily-report` | Daily grouped report: pause, increase, negative, create ads |
| POST | `/ai/generate-ads` | Generate 15 headlines and 4 descriptions |
| POST | `/ai/search-campaign-optimizer` | Return senior Google Ads Search optimization JSON |
| POST | `/audit/landing-page` | Audit SEO, UX, CTA, content, speed and mobile |
| POST | `/predictions/conversion` | Predict conversion probability and bid action |
| POST | `/google-ads/campaigns/publish` | Validate or publish a Search campaign with exact match keywords, manual CPC and excluded locations |
| POST | `/google-ads/campaigns/auto-publish` | Generate copy from landing page input, then validate or publish the campaign |
| GET | `/affiliate/programs` | List configured affiliate networks, domains and parameters |
| POST | `/affiliate/wrap` | Convert an original URL into an affiliate URL with duplicate protection and optional short tracking link |
| GET | `/affiliate/r/{code}` | Redirect tracking endpoint that logs clicks and forwards to the affiliate URL |
| GET | `/affiliate/stats/{code}` | Return click count and metadata for a short affiliate link |

## Example Payloads

```json
POST /ai/generate-ads
{
  "product_name": "Cloud Backup",
  "website": "https://example.com",
  "landing_page_url": "https://example.com/cloud-backup",
  "language": "English",
  "target_audience": "IT managers",
  "primary_offer": "free backup assessment",
  "primary_cta": "Get Assessment"
}
```

`/ai/generate-ads` reads the landing page URL, extracts title, meta description, headings and page text, then generates English Google Ads content aligned with the page.

```json
POST /ai/search-campaign-optimizer
{
  "campaign_name": "Search - Cloud Backup",
  "product_name": "Cloud Backup",
  "landing_page_url": "https://example.com/cloud-backup",
  "target_audience": "IT managers",
  "target_keywords": ["cloud backup", "business backup software"],
  "language": "English",
  "keywords": [],
  "search_terms": [],
  "daily_performance": []
}
```

Returns JSON keys: `summary`, `wasted_spend_findings`, `growth_opportunities`, `negative_keywords`, `bid_adjustments`, `campaign_actions`, `landing_page_alignment`, `generated_search_ads`, `priority_score`, `expected_impact`.

```json
POST /predictions/conversion
{
  "ctr": 8.4,
  "cpc": 4200,
  "device": "desktop",
  "audience": "in-market buyer",
  "hour": 10,
  "day": 2
}
```

```json
POST /google-ads/campaigns/publish
{
  "campaign_name": "Search - AI Google Ads Optimizer",
  "daily_budget_vnd": 300000,
  "manual_cpc_bid_vnd": 5000,
  "landing_page_url": "https://example.com/google-ads-optimizer",
  "target_location": "Vietnam",
  "excluded_locations": ["Ho Chi Minh City", "Ha Noi"],
  "excluded_location_ids": [1028581],
  "keywords": ["google ads optimizer", "toi uu google ads"],
  "headlines": ["Toi Uu Google Ads", "Giam CPC Hom Nay", "Tang ROAS Nhanh"],
  "descriptions": [
    "Tao campaign search voi keyword exact match va bid thu cong.",
    "Validate budget, location loai tru va copy truoc khi dang live."
  ],
  "dry_run": true
}
```

```json
POST /affiliate/wrap
{
  "url": "https://www.amazon.com/dp/B08N5WRWNW",
  "use_redirect_tracking": true,
  "shorten": true,
  "public_base_url": "https://go.yourdomain.com",
  "sub_id": "content-tool",
  "campaign": "rsa-architect"
}
```

Affiliate programs are configured in `backend/app/config/affiliate_programs.json`. Click counters and short-link mappings are stored under `backend/data/`.
If you do not have a public tracking domain, copy and use `affiliate_url` instead of the localhost `short_url`.

Standalone Flask API:

```bash
cd backend
venv\\Scripts\\python.exe -m app.flask_affiliate_api
```

Flask endpoints: `POST /affiliate/wrap`, `GET /affiliate/programs`, `GET /affiliate/r/<code>`, `GET /affiliate/stats/<code>`.
