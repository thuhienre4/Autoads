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

### Content win templates

In **RSA Content Inputs → Content win · Google Ads**, choose **Chọn file content
win từ máy** or drag a local `.xlsx`, `.csv`, `.txt` or `.json` file into the upload
area (up to 5 MB). Excel/CSV files can contain up to 50 winning ads: one ad per
row, with columns `Headline 1`…`Headline 15` and `Description 1`…`Description 4`.
Vietnamese headers (`Tiêu đề 1`, `Mô tả 1`) and combined `Headlines` /
`Descriptions` cells separated by line breaks are also accepted. CSV supports
UTF-8/UTF-16 and comma, semicolon or tab delimiters. Visible Excel sheets are read;
formulas must be replaced with text before saving. Legacy `.xls` files must be
saved as `.xlsx` first.

The upload area includes a CSV example that opens in Excel. Review each imported
ad, correct any highlighted errors, select the templates to keep and choose
**Lưu N mẫu đã chọn**. Saving multiple templates is atomic: invalid templates do
not cause partial imports. The first saved template is selected for generation.
You can also expand **Hoặc dán content win trực tiếp** to enter a single example.
TXT files use `[Headlines]` and `[Descriptions]` sections with one asset per line.
Each template accepts 1–15 headlines (30 characters each), 1–4 descriptions
(90 characters each), a name and optional notes. Saving a template does not call AI.

The selected template is analyzed into reusable sentence scaffolds, tone and
CTA patterns. The profile is cached in SQLite by template content, model and
algorithm version. The writer receives the abstract profile and facts from the
**new** project; original template ads, brand lists and offer lists are not
included in the writing prompt. This is reference-based generation, not model
fine-tuning. Changing landing pages reuses style, never cached product facts.

Each generated asset cites target fact IDs. Local checks reject invalid lengths,
duplicates, unknown evidence IDs, unsupported numeric units and source-only brand
names. A separate AI review checks meaning, claims, language and style against
the target facts. A failed draft gets one repair attempt and another review;
unresolved errors return an explicit failure instead of unchecked copy. If the
landing page cannot be read, a substantive manual brief is required. Keywords,
audience, tone and CTA preferences do not count as evidence for factual offers.

The result shows the template name, writing patterns and expandable source facts.
Manual edits invalidate the displayed review status. Reviews reduce mistakes but
do not establish factual truth, Google Ads approval or conversion performance.
The first use normally requires three model calls (style, writing, review), then
two with a cached profile; a repair can add up to two calls. This adds latency
and API usage compared with the previous single-call generation.
The bulk CSV editor also supports selecting a template for the next batch of
AI suggestions; existing text is replaced only when a suggestion is accepted.

Template generation requires `AI_PROVIDER=openai`, `OPENAI_API_KEY` and a
Structured Outputs compatible `OPENAI_MODEL` (default `gpt-4o-mini`). Provider
or validation failures are reported explicitly. Without a selected template,
the existing rule-based generation is retained. Generated claims still need
review before publishing; style matching does not guarantee ad performance.

Templates are shared by this application instance and persist in SQLite at
`WIN_TEMPLATE_STORE_PATH`, or `win_templates.sqlite3` on the Railway volume,
or `backend/data/win_templates.sqlite3` locally. Keep this file on persistent
storage and include it in backups. The API follows the app's existing access
model; it does not add separate user libraries.

API: `GET/POST /api/v1/ai/win-templates`,
`DELETE /api/v1/ai/win-templates/{id}`. Supply `win_template_id` to
`POST /api/v1/ai/generate-ads` to apply a saved example.
`POST /api/v1/ai/win-templates/preview` accepts a multipart `file` (Excel/CSV)
and returns editable drafts without saving or calling AI.
`POST /api/v1/ai/win-templates/batch` accepts 1–50 validated template objects.
The integration uses [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

Single and bulk campaign editors expose the same match-type checkboxes (Exact,
Phrase and Broad) and network switches (Google search partners and Display).
Exact and Phrase can be selected together. Google Search remains enabled for
Search campaigns. Bulk edits reset approval, and selections are carried through
draft validation, publishing and scheduled campaigns.

The MVP has deterministic optimization rules and AI-ready service boundaries:

- Wasted keywords: high cost with low or zero conversions.
- Growth keywords: high CTR, low/acceptable CPC, high conversions and ROAS.
- Search term mining: long-tail, commercial and buyer-intent phrases.
- Negative keyword detection: free, torrent, job, career, tutorial, download, crack.
- Ad copy generation: 15 headlines and 4 descriptions aligned with Google Ads limits.
- Landing page audit: SEO, UX, conversion and mobile scoring.
- Conversion prediction: probability scoring based on CTR, CPC, device, audience, hour and day.
