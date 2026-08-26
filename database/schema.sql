-- PostgreSQL Schema for AI Google Ads Optimizer

-- Users Table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    google_id VARCHAR(255) UNIQUE,
    google_ads_customer_id VARCHAR(255),
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Campaigns Table
CREATE TABLE campaigns (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    google_campaign_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50),
    budget_amount DECIMAL(15, 2),
    budget_period VARCHAR(50),
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, google_campaign_id)
);

-- Ad Groups Table
CREATE TABLE ad_groups (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    google_ad_group_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50),
    cpc_bid DECIMAL(10, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campaign_id, google_ad_group_id)
);

-- Keywords Table
CREATE TABLE keywords (
    id SERIAL PRIMARY KEY,
    ad_group_id INTEGER NOT NULL REFERENCES ad_groups(id) ON DELETE CASCADE,
    google_keyword_id VARCHAR(255) NOT NULL,
    keyword_text VARCHAR(255) NOT NULL,
    match_type VARCHAR(50),
    status VARCHAR(50),
    bid DECIMAL(10, 4),
    clicks BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    cost DECIMAL(15, 2) DEFAULT 0,
    conversions DECIMAL(10, 2) DEFAULT 0,
    conversion_value DECIMAL(15, 2) DEFAULT 0,
    quality_score INTEGER,
    ctr DECIMAL(5, 2),
    cpc DECIMAL(10, 4),
    roas DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ad_group_id, google_keyword_id)
);

-- Search Terms Table
CREATE TABLE search_terms (
    id SERIAL PRIMARY KEY,
    ad_group_id INTEGER NOT NULL REFERENCES ad_groups(id) ON DELETE CASCADE,
    search_term VARCHAR(500) NOT NULL,
    clicks BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    cost DECIMAL(15, 2) DEFAULT 0,
    conversions DECIMAL(10, 2) DEFAULT 0,
    conversion_value DECIMAL(15, 2) DEFAULT 0,
    ctr DECIMAL(5, 2),
    cpc DECIMAL(10, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily Performance Data
CREATE TABLE daily_performance (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    clicks BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    cost DECIMAL(15, 2) DEFAULT 0,
    conversions DECIMAL(10, 2) DEFAULT 0,
    conversion_value DECIMAL(15, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campaign_id, date)
);

-- Keywords Performance by Date
CREATE TABLE keyword_daily_performance (
    id SERIAL PRIMARY KEY,
    keyword_id INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    clicks BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    cost DECIMAL(15, 2) DEFAULT 0,
    conversions DECIMAL(10, 2) DEFAULT 0,
    conversion_value DECIMAL(15, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(keyword_id, date)
);

-- Conversions Table
CREATE TABLE conversions (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    keyword_id INTEGER REFERENCES keywords(id) ON DELETE SET NULL,
    conversion_id VARCHAR(255),
    conversion_date TIMESTAMP,
    value DECIMAL(15, 2),
    currency VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Negative Keywords
CREATE TABLE negative_keywords (
    id SERIAL PRIMARY KEY,
    ad_group_id INTEGER REFERENCES ad_groups(id) ON DELETE CASCADE,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    keyword_text VARCHAR(255) NOT NULL,
    match_type VARCHAR(50),
    reason VARCHAR(255),
    suggested_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campaign_id, keyword_text)
);

-- AI Recommendations
CREATE TABLE recommendations (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    keyword_id INTEGER REFERENCES keywords(id) ON DELETE CASCADE,
    ad_group_id INTEGER REFERENCES ad_groups(id) ON DELETE CASCADE,
    recommendation_type VARCHAR(100),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    priority VARCHAR(50),
    status VARCHAR(50) DEFAULT 'pending',
    impact_score DECIMAL(5, 2),
    estimated_impact TEXT,
    action_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_at TIMESTAMP,
    UNIQUE(campaign_id, keyword_id, recommendation_type)
);

-- AI Reports
CREATE TABLE ai_reports (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    report_date DATE NOT NULL,
    report_type VARCHAR(100),
    title VARCHAR(255) NOT NULL,
    data JSONB,
    summary TEXT,
    recommendations_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, campaign_id, report_date)
);

-- Landing Page Audits
CREATE TABLE landing_page_audits (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    campaign_id INTEGER REFERENCES campaigns(id) ON DELETE CASCADE,
    url VARCHAR(500) NOT NULL,
    seo_score DECIMAL(5, 2),
    ux_score DECIMAL(5, 2),
    conversion_score DECIMAL(5, 2),
    mobile_score DECIMAL(5, 2),
    overall_score DECIMAL(5, 2),
    recommendations JSONB,
    load_time_ms INTEGER,
    mobile_friendly BOOLEAN,
    crawlable BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Ad Creatives
CREATE TABLE ad_creatives (
    id SERIAL PRIMARY KEY,
    ad_group_id INTEGER NOT NULL REFERENCES ad_groups(id) ON DELETE CASCADE,
    headline_1 VARCHAR(255),
    headline_2 VARCHAR(255),
    headline_3 VARCHAR(255),
    description_1 VARCHAR(500),
    description_2 VARCHAR(500),
    description_3 VARCHAR(500),
    final_url VARCHAR(500),
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AI Generated Ad Suggestions
CREATE TABLE ai_ad_suggestions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    product_name VARCHAR(255),
    website_url VARCHAR(500),
    landing_page_url VARCHAR(500),
    headlines JSONB,
    descriptions JSONB,
    cta_suggestions JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Conversion Prediction
CREATE TABLE conversion_predictions (
    id SERIAL PRIMARY KEY,
    keyword_id INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    prediction_date DATE,
    ctr DECIMAL(5, 2),
    cpc DECIMAL(10, 4),
    device VARCHAR(50),
    audience_type VARCHAR(100),
    hour_of_day INTEGER,
    day_of_week INTEGER,
    predicted_conversion_probability DECIMAL(5, 2),
    recommendation VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- API Sync Log
CREATE TABLE api_sync_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entity_type VARCHAR(100),
    sync_type VARCHAR(50),
    status VARCHAR(50),
    records_synced INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_campaigns_user_id ON campaigns(user_id);
CREATE INDEX idx_ad_groups_campaign_id ON ad_groups(campaign_id);
CREATE INDEX idx_keywords_ad_group_id ON keywords(ad_group_id);
CREATE INDEX idx_keywords_status ON keywords(status);
CREATE INDEX idx_search_terms_ad_group_id ON search_terms(ad_group_id);
CREATE INDEX idx_daily_performance_campaign_date ON daily_performance(campaign_id, date);
CREATE INDEX idx_keyword_daily_perf_keyword_date ON keyword_daily_performance(keyword_id, date);
CREATE INDEX idx_conversions_campaign_id ON conversions(campaign_id);
CREATE INDEX idx_recommendations_campaign_id ON recommendations(campaign_id);
CREATE INDEX idx_recommendations_status ON recommendations(status);
CREATE INDEX idx_ai_reports_user_campaign_date ON ai_reports(user_id, campaign_id, report_date);
CREATE INDEX idx_landing_page_audits_user_id ON landing_page_audits(user_id);
CREATE INDEX idx_api_sync_log_user_date ON api_sync_log(user_id, created_at);
