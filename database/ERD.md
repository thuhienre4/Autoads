# Entity Relationship Diagram

```mermaid
erDiagram
  users ||--o{ campaigns : owns
  users ||--o{ landing_page_audits : runs
  users ||--o{ ai_reports : receives
  users ||--o{ ai_ad_suggestions : requests
  users ||--o{ api_sync_log : has

  campaigns ||--o{ ad_groups : contains
  campaigns ||--o{ daily_performance : tracks
  campaigns ||--o{ conversions : records
  campaigns ||--o{ recommendations : receives
  campaigns ||--o{ negative_keywords : excludes
  campaigns ||--o{ ai_reports : summarized_by
  campaigns ||--o{ landing_page_audits : audited_by
  campaigns ||--o{ ai_ad_suggestions : uses

  ad_groups ||--o{ keywords : contains
  ad_groups ||--o{ search_terms : receives
  ad_groups ||--o{ ad_creatives : contains
  ad_groups ||--o{ recommendations : receives
  ad_groups ||--o{ negative_keywords : optionally_scopes

  keywords ||--o{ keyword_daily_performance : tracks
  keywords ||--o{ conversions : attributes
  keywords ||--o{ recommendations : receives
  keywords ||--o{ conversion_predictions : predicts

  users {
    int id PK
    varchar email UK
    varchar name
    varchar google_id UK
    varchar google_ads_customer_id
    text access_token
    text refresh_token
    timestamp token_expires_at
  }

  campaigns {
    int id PK
    int user_id FK
    varchar google_campaign_id
    varchar name
    varchar status
    decimal budget_amount
    date start_date
    date end_date
  }

  ad_groups {
    int id PK
    int campaign_id FK
    varchar google_ad_group_id
    varchar name
    varchar status
    decimal cpc_bid
  }

  keywords {
    int id PK
    int ad_group_id FK
    varchar google_keyword_id
    varchar keyword_text
    varchar match_type
    varchar status
    decimal bid
    bigint clicks
    bigint impressions
    decimal cost
    decimal conversions
    decimal conversion_value
    int quality_score
    decimal ctr
    decimal cpc
    decimal roas
  }

  search_terms {
    int id PK
    int ad_group_id FK
    varchar search_term
    bigint clicks
    bigint impressions
    decimal cost
    decimal conversions
    decimal conversion_value
    decimal ctr
    decimal cpc
  }

  conversions {
    int id PK
    int campaign_id FK
    int keyword_id FK
    varchar conversion_id
    timestamp conversion_date
    decimal value
    varchar currency
  }

  recommendations {
    int id PK
    int campaign_id FK
    int keyword_id FK
    int ad_group_id FK
    varchar recommendation_type
    varchar title
    text description
    varchar priority
    varchar status
    decimal impact_score
  }

  ai_reports {
    int id PK
    int user_id FK
    int campaign_id FK
    date report_date
    varchar report_type
    jsonb data
    text summary
  }
```

## Core Relationships

| From | To | Type | Purpose |
|---|---|---|---|
| users | campaigns | 1:N | One advertiser can connect many Google Ads campaigns |
| campaigns | ad_groups | 1:N | Campaign structure from Google Ads |
| ad_groups | keywords | 1:N | Keyword performance and optimization unit |
| ad_groups | search_terms | 1:N | Raw query mining for new and negative keywords |
| campaigns | daily_performance | 1:N | Dashboard trend metrics by day |
| keywords | keyword_daily_performance | 1:N | Keyword-level history and ML features |
| campaigns/keywords/ad_groups | recommendations | 1:N | AI optimization actions |
| users/campaigns | ai_reports | 1:N | Daily automated optimization report |

## Design Notes

- `user_id` enforces tenant ownership.
- Google Ads external IDs are stored separately from internal primary keys.
- JSONB is used for flexible AI artifacts such as reports, ad suggestions and audit findings.
- Daily fact tables support date filters: 7 days, 30 days, 90 days and custom ranges.
