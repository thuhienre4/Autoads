# AI Google Ads Optimizer

Full-stack MVP for analyzing Google Ads campaigns, detecting wasted spend, finding growth keywords, suggesting negative keywords, generating ad copy, auditing landing pages and predicting conversion probability.

## Tech Stack

- Frontend: React, TailwindCSS, Recharts, lucide-react
- Backend: Python FastAPI
- Database: PostgreSQL
- AI-ready integrations: OpenAI API or Gemini API
- HTTP-first landing-page reader with Playwright/Chromium fallback for JavaScript-rendered sites
- Auth-ready integration: Google OAuth
- Deployment: Docker Compose, Render or VPS

## File Structure

```text
ai-google-ads-optimizer/
  backend/
    app/
      api/routes/          FastAPI route modules
      core/config.py       Environment configuration
      schemas/ads.py       Pydantic DTOs
      services/            AI, analysis and sample data logic
      utils/database.py    Async SQLAlchemy setup
    Dockerfile
    requirements.txt
  frontend/
    src/main.jsx           Dashboard application
    src/styles/index.css   Tailwind entry
    Dockerfile
    package.json
  database/
    schema.sql             PostgreSQL schema
    ERD.md                 Mermaid ERD and relationship notes
  docs/
    API_ENDPOINTS.md
  docker-compose.yml
```

## Local Setup

### Docker

```bash
docker compose up --build
```

Then open:

- Frontend: `http://localhost:5173`
- Backend docs: `http://localhost:8000/api/docs`
- Health check: `http://localhost:8000/health`

### Manual Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
uvicorn app.main:app --reload
```

### Manual Frontend

```bash
cd frontend
npm install
npm run dev
```

## Production Configuration

Set these environment variables in Render, VPS, or your container platform:

```text
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DB
JWT_SECRET=<strong-secret>
CORS_ORIGINS=https://your-frontend-domain.com
GOOGLE_CLIENT_ID=<google-oauth-client-id>
GOOGLE_CLIENT_SECRET=<google-oauth-client-secret>
GOOGLE_REDIRECT_URI=https://your-api-domain.com/api/v1/auth/google/callback
GOOGLE_ADS_DEVELOPER_TOKEN=<developer-token>
GOOGLE_ADS_LOGIN_CUSTOMER_ID=<manager-account-id>
OPENAI_API_KEY=<openai-key>
AI_PROVIDER=openai
ENABLE_HEADLESS_BROWSER=true
```

The page reader first parses normal HTML. When the response is empty, is only a
JavaScript shell, or has low extraction confidence, it renders the page with
headless Chromium and extracts the final DOM. API responses expose
`page_context.fetch_method` (`http` or `playwright`) for diagnostics.

For Render:

1. Create a PostgreSQL instance.
2. Create a backend Web Service from `backend/Dockerfile`.
3. Create a frontend Static Site or Docker service from `frontend/Dockerfile`.
4. Set `VITE_API_BASE_URL` to the backend public URL plus `/api/v1`.
5. Add Google OAuth authorized redirect URI for the backend callback URL.

### Railway deployment with persistent MCC login

The root `Dockerfile` builds the React frontend and serves it from the FastAPI
service, so Railway only needs one public application service.

1. Deploy this repository as a Railway service and generate a public domain.
2. Add a Railway Volume to that service. Mount it at `/data`. Railway supplies
   `RAILWAY_VOLUME_MOUNT_PATH`, and the application stores the Google OAuth
   session there automatically.
3. Add a Railway PostgreSQL service and set the application variable
   `DATABASE_URL=${{Postgres.DATABASE_URL}}` (replace `Postgres` if the database
   service has another name).
4. Configure these application variables in Railway:

```text
ENVIRONMENT=production
DEBUG=false
GOOGLE_CLIENT_ID=<google-oauth-client-id>
GOOGLE_CLIENT_SECRET=<google-oauth-client-secret>
GOOGLE_ADS_DEVELOPER_TOKEN=<developer-token>
GOOGLE_ADS_LOGIN_CUSTOMER_ID=<manager-account-id-without-dashes>
GOOGLE_ADS_CUSTOMER_IDS=<optional-comma-separated-client-ids>
ENABLE_LIVE_GOOGLE_ADS_MUTATIONS=false
```

`FRONTEND_URL` and `GOOGLE_REDIRECT_URI` are derived automatically from
Railway's `RAILWAY_PUBLIC_DOMAIN`. In Google Cloud Console, add this exact
authorized redirect URI:

```text
https://<your-railway-domain>/api/v1/auth/google/callback
```

After the first **Connect Google Ads** consent, the refresh token is stored on
the mounted volume and is reused after Railway restarts and redeployments. Keep
the volume attached and never commit its session file or OAuth secrets.

For a VPS:

1. Install Docker and Docker Compose.
2. Copy the project to the server.
3. Replace `.env.example` with production `.env` values.
4. Run `docker compose up -d --build`.
5. Put Nginx/Caddy in front with HTTPS.

## Google Ads Integration Notes

The current implementation includes demo endpoints and data so the product can be reviewed immediately. To connect live Google Ads data, implement the sync service with the official Google Ads Python client using these entities:

- Campaign
- Ad Group
- Keyword
- Search Term
- Clicks, Impressions, CTR, CPC, Cost
- Conversions, Conversion Value, ROAS
- Quality Score

Persist the results into `campaigns`, `ad_groups`, `keywords`, `search_terms`, `daily_performance`, and `keyword_daily_performance`.

## AI Logic

The MVP has deterministic optimization rules and AI-ready service boundaries:

- Wasted keywords: high cost with low or zero conversions.
- Growth keywords: high CTR, low/acceptable CPC, high conversions and ROAS.
- Search term mining: long-tail, commercial and buyer-intent phrases.
- Negative keyword detection: free, torrent, job, career, tutorial, download, crack.
- Ad copy generation: 15 headlines and 4 descriptions aligned with Google Ads limits.
- Landing page audit: SEO, UX, conversion and mobile scoring.
- Conversion prediction: probability scoring based on CTR, CPC, device, audience, hour and day.
