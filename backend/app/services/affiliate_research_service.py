import csv
import html
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from urllib.parse import urlparse

import httpx
import certifi
import urllib3

from app.core.config import settings
from app.services.google_search_service import fallback_web_search, search_google
from app.services.page_reader import render_page_async


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
REPORTS_PATH = DATA_DIR / "affiliate_research_reports.json"

AFFILIATE_TERMS = (
    "affiliate",
    "affiliates",
    "affiliate program",
    "partner program",
    "partners",
    "referral",
    "refer a friend",
    "commission",
    "publisher",
)

SIGNUP_TERMS = (
    "sign up",
    "signup",
    "register",
    "registration",
    "create account",
    "join",
    "start free",
    "free trial",
    "get started",
    "pricing",
)

NOISE_DOMAINS = (
    "google.",
    "youtube.",
    "facebook.",
    "linkedin.",
    "twitter.",
    "x.com",
    "instagram.",
    "wikipedia.",
    "crunchbase.",
    "g2.",
    "capterra.",
    "trustpilot.",
    "producthunt.",
    "reddit.",
)


class TextExtractor(HTMLParser):
    VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    def __init__(self):
        super().__init__()
        self.skip_stack = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if self.skip_stack:
            if tag not in self.VOID_TAGS:
                self.skip_stack.append(tag)
        elif tag in {"script", "style", "noscript", "svg", "template"}:
            self.skip_stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.skip_stack:
            while self.skip_stack:
                skipped = self.skip_stack.pop()
                if skipped == tag:
                    break

    def handle_data(self, data):
        if not self.skip_stack:
            text = data.strip()
            if text:
                self.parts.append(text)

    def text(self):
        return " ".join(self.parts)


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_reports() -> list[dict]:
    if not REPORTS_PATH.exists():
        return []
    try:
        data = json.loads(REPORTS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _write_reports(reports: list[dict]) -> None:
    _ensure_data_dir()
    REPORTS_PATH.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")


def _clean_project_names(project_names: list[str]) -> list[str]:
    seen = set()
    cleaned = []
    for name in project_names:
        value = str(name or "").strip()
        if not value or value.lower() in seen:
            continue
        seen.add(value.lower())
        cleaned.append(value)
    return cleaned[:50]


def _domain_from_url(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host[4:] if host.startswith("www.") else host


def _root_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        return ""
    return f"{parsed.scheme}://{_domain_from_url(url)}"


def _score_text(text: str) -> tuple[int, list[str]]:
    lowered = text.lower()
    matched = sorted({term for term in AFFILIATE_TERMS if term in lowered})
    score = min(100, len(matched) * 18)
    if "affiliate program" in lowered:
        score += 25
    if "commission" in lowered:
        score += 10
    if "partner program" in lowered:
        score += 15
    return min(score, 100), matched


def _score_signup_text(text: str) -> tuple[int, list[str]]:
    lowered = text.lower()
    matched = sorted({term for term in SIGNUP_TERMS if term in lowered})
    score = min(100, len(matched) * 18)
    if "sign up" in lowered or "signup" in lowered or "register" in lowered:
        score += 25
    if "free trial" in lowered or "get started" in lowered:
        score += 15
    return min(score, 100), matched


def _score_official_candidate(project_name: str, title: str, url: str, snippet: str = "") -> int:
    slug = _project_slug(project_name)
    domain = _domain_from_url(url).lower()
    parsed = urlparse(url)
    if not slug or not domain:
        return 0
    if any(noise in domain for noise in NOISE_DOMAINS):
        return 0
    score = 0
    compact_domain = re.sub(r"[^a-z0-9]+", "", domain.split(":")[0])
    text = f"{title} {snippet} {domain}".lower()
    if slug in compact_domain:
        score += 80
    if compact_domain.startswith(slug):
        score += 15
    if project_name.lower() in text:
        score += 10
    if parsed.path in {"", "/"}:
        score += 10
    return min(score, 100)


async def _google_search(client: httpx.AsyncClient, query: str, max_results: int) -> list[dict]:
    if not settings.GOOGLE_SEARCH_API_KEY or not settings.GOOGLE_SEARCH_ENGINE_ID:
        raise RuntimeError("Missing GOOGLE_SEARCH_API_KEY or GOOGLE_SEARCH_ENGINE_ID in backend .env")
    try:
        result = await search_google(query, max_results=max_results)
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("error", {}).get("message", "")
        except Exception:
            pass
        if exc.response.status_code == 403 and "Custom Search JSON API" in detail:
            result = await fallback_web_search(query, max_results=max_results)
        else:
            raise
    return [
        {
            "title": item["title"],
            "link": item["url"],
            "snippet": item["snippet"],
        }
        for item in result["items"]
    ]


async def _fetch_page_text(client: httpx.AsyncClient, url: str) -> str:
    try:
        response = await client.get(url, follow_redirects=True, timeout=5)
        content_type = response.headers.get("content-type", "")
        if response.status_code >= 400 or "text/html" not in content_type:
            return ""
        extractor = TextExtractor()
        extractor.feed(response.text[:300000])
        return html.unescape(re.sub(r"\s+", " ", extractor.text())).strip()[:12000]
    except Exception:
        return ""


async def _fetch_page_text_insecure(url: str) -> str:
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        async with httpx.AsyncClient(
            headers={"User-Agent": "AdsPulse Affiliate Research/1.0"},
            verify=False,
        ) as client:
            return await _fetch_page_text(client, url)
    except Exception:
        return ""


def _extract_page_text(html_source: str) -> str:
    extractor = TextExtractor()
    extractor.feed(html_source[: settings.PAGE_READER_MAX_HTML_CHARS])
    return html.unescape(re.sub(r"\s+", " ", extractor.text())).strip()[:12000]


async def _read_page_text(client: httpx.AsyncClient, url: str) -> tuple[str, str, str]:
    """Read real page content, rendering JavaScript when static HTML is sparse."""
    static_text = await _fetch_page_text(client, url)
    if len(static_text.split()) >= settings.PAGE_READER_MIN_WORDS:
        return static_text, "http", ""

    rendered = await render_page_async(url)
    if rendered.html:
        rendered_text = _extract_page_text(rendered.html)
        if len(rendered_text) >= len(static_text):
            return rendered_text, "playwright", ""
    return static_text, "http", rendered.error


async def _url_accessible(client: httpx.AsyncClient, url: str) -> bool:
    try:
        response = await client.get(url, follow_redirects=True, timeout=4)
        return response.status_code < 400
    except Exception:
        return False


def _project_slug(project_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", project_name.lower())


def _score_url_candidate(project_name: str, url: str) -> tuple[int, list[str]]:
    slug = _project_slug(project_name)
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    if not slug or slug not in host:
        return 0, []
    if any(term in path for term in ("affiliate", "affiliates")):
        return 85, ["affiliate", "affiliate program"]
    if any(term in path for term in ("partner", "partners")):
        return 70, ["partners", "partner program"]
    if any(term in path for term in ("referral", "refer")):
        return 55, ["referral"]
    return 0, []


def _score_signup_url_candidate(project_name: str, url: str) -> tuple[int, list[str]]:
    slug = _project_slug(project_name)
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    if not slug or slug not in re.sub(r"[^a-z0-9]+", "", host):
        return 0, []
    if any(term in path for term in ("signup", "sign-up", "register", "registration")):
        return 90, ["sign up", "register"]
    if any(term in path for term in ("pricing", "free-trial", "trial", "get-started")):
        return 70, ["pricing", "free trial"]
    if "login" in path:
        return 45, ["login"]
    return 0, []


def _best_official_domain_from_items(project_name: str, items: list[dict]) -> str | None:
    best_score = 0
    best_domain = None
    for item in items:
        title = item.get("title") or ""
        link = item.get("link") or item.get("url") or ""
        snippet = item.get("snippet") or ""
        score = _score_official_candidate(project_name, title, link, snippet)
        domain = _domain_from_url(link)
        if score > best_score and domain:
            best_score = score
            best_domain = domain
    return best_domain if best_score >= 70 else None


async def _probe_common_project_pages(client: httpx.AsyncClient, project_name: str, domains: list[str] | None = None) -> list[dict]:
    slug = _project_slug(project_name)
    if not slug:
        return []
    domains = domains or []
    if not domains:
        return []
    paths = [
        "/",
        "/signup/",
        "/sign-up/",
        "/register/",
        "/registration/",
        "/get-started/",
        "/pricing/",
        "/login/",
        "/affiliate/",
        "/affiliates/",
        "/partners/",
        "/referral/",
    ]
    candidates = []
    for domain in domains:
        for path in paths:
            url = f"https://{domain}{path}"
            page_text = ""
            affiliate_score, affiliate_terms = 0, []
            signup_score, signup_terms = 0, []
            url_affiliate_score, url_affiliate_terms = _score_url_candidate(project_name, url)
            url_signup_score, url_signup_terms = _score_signup_url_candidate(project_name, url)
            official_score = _score_official_candidate(project_name, project_name, url, page_text[:300])
            if not any((affiliate_score, signup_score, url_affiliate_score, url_signup_score, official_score)):
                continue
            if path != "/" and not await _url_accessible(client, url):
                continue
            candidates.append(
                {
                    "source": "direct_probe",
                    "title": f"{project_name} {path.strip('/').replace('-', ' ').title() or 'Official Website'}",
                    "link": url,
                    "snippet": page_text[:220],
                    "score": max(affiliate_score, url_affiliate_score),
                    "matched_terms": sorted(set(affiliate_terms + url_affiliate_terms)),
                    "signup_score": max(signup_score, url_signup_score),
                    "signup_terms": sorted(set(signup_terms + url_signup_terms)),
                    "official_score": official_score,
                }
            )
    return candidates


async def _probe_common_affiliate_pages(client: httpx.AsyncClient, project_name: str, domains: list[str] | None = None) -> list[dict]:
    slug = _project_slug(project_name)
    if not slug:
        return []
    domains = domains or []
    if not domains:
        return []
    paths = ["/affiliate/", "/affiliates/", "/partners/", "/partner/", "/referral/", "/refer/"]
    candidates = []
    for domain in domains:
        for path in paths:
            url = f"https://{domain}{path}"
            if not await _url_accessible(client, url):
                continue
            page_text, fetch_method, fetch_error = await _read_page_text(client, url)
            if not page_text:
                page_text = await _fetch_page_text_insecure(url)
                fetch_method = "http_insecure" if page_text else fetch_method
            score, matched_terms = _score_text(page_text)
            url_score, url_terms = _score_url_candidate(project_name, url)
            score = max(score, url_score)
            matched_terms = sorted(set(matched_terms + url_terms))
            if score <= 0:
                continue
            candidates.append(
                {
                    "title": f"{project_name} {path.strip('/').replace('-', ' ').title()}",
                    "link": url,
                    "snippet": page_text[:220],
                    "score": score,
                    "matched_terms": matched_terms,
                    "fetch_method": fetch_method,
                    "fetch_error": fetch_error,
                }
            )
            if score >= 70:
                return candidates
    return candidates


async def _research_one_project(client: httpx.AsyncClient, project_name: str, max_results: int) -> dict:
    query = f'"{project_name}" official website sign up register affiliate program partner program'
    items = []
    items.extend(await _google_search(client, query, max_results))
    search_official_domain = _best_official_domain_from_items(project_name, items)
    probe_domains = [search_official_domain] if search_official_domain else []
    probed_items = await _probe_common_project_pages(client, project_name, domains=probe_domains)
    items.extend(probed_items)
    if not items:
        items = await _probe_common_affiliate_pages(client, project_name, domains=probe_domains)
    candidates = []
    best_score = 0
    best_url = None
    best_terms = []
    best_official_score = 0
    official_url = None
    official_domain = None
    best_signup_score = 0
    signup_url = None
    signup_terms = []
    seen_urls = set()

    async def evaluate_items(result_items: list[dict]) -> None:
        nonlocal best_score, best_url, best_terms, best_official_score
        nonlocal official_url, official_domain, best_signup_score, signup_url, signup_terms
        for item in result_items:
            title = item.get("title") or ""
            link = item.get("link") or item.get("url") or ""
            if not link or link in seen_urls:
                continue
            seen_urls.add(link)
            snippet = item.get("snippet") or ""
            probed_score = int(item.get("score") or 0)
            probed_terms = item.get("matched_terms") or []
            probed_signup_score = int(item.get("signup_score") or 0)
            probed_signup_terms = item.get("signup_terms") or []
            probed_official_score = int(item.get("official_score") or 0)
            text_score, terms = _score_text(f"{title} {snippet} {link}")
            signup_text_score, text_signup_terms = _score_signup_text(f"{title} {snippet} {link}")
            official_score = max(probed_official_score, _score_official_candidate(project_name, title, link, snippet))
            page_text, fetch_method, fetch_error = await _read_page_text(client, link)
            page_score, page_terms = _score_text(page_text)
            page_signup_score, page_signup_terms = _score_signup_text(page_text)
            score = max(text_score, page_score, probed_score)
            matched_terms = sorted(set(terms + page_terms + probed_terms))
            signup_score = max(signup_text_score, page_signup_score, probed_signup_score)
            item_signup_terms = sorted(set(text_signup_terms + page_signup_terms + probed_signup_terms))
            official_score = max(official_score, _score_official_candidate(project_name, title, link, page_text[:300]))
            candidate = {
                "source": item.get("source") or "search",
                "title": title,
                "url": link,
                "domain": _domain_from_url(link),
                "snippet": snippet,
                "score": score,
                "matched_terms": matched_terms,
                "official_score": official_score,
                "signup_score": signup_score,
                "signup_terms": item_signup_terms,
                "fetch_method": fetch_method,
                "fetch_error": fetch_error,
            }
            candidates.append(candidate)
            if official_score > best_official_score:
                best_official_score = official_score
                official_url = _root_url(link) or link
                official_domain = _domain_from_url(link)
            if signup_score > best_signup_score and official_score >= 60:
                best_signup_score = signup_score
                signup_url = link
                signup_terms = item_signup_terms
            if score > best_score:
                best_score = score
                best_url = link
                best_terms = matched_terms

    await evaluate_items(items)
    if best_score < 70:
        probed_items = await _probe_common_affiliate_pages(client, project_name, domains=[official_domain] if official_domain else probe_domains)
        await evaluate_items([item for item in probed_items if item.get("link") not in seen_urls])

    candidates.sort(
        key=lambda item: (
            item.get("score", 0),
            item.get("signup_score", 0),
            item.get("official_score", 0),
        ),
        reverse=True,
    )
    if official_domain:
        candidates = [
            candidate
            for candidate in candidates
            if (
                candidate.get("source") != "direct_probe"
                or candidate.get("domain") == official_domain
            )
        ]
    candidates = candidates[:12]

    if best_score >= 70:
        status = "likely_affiliate"
    elif best_score >= 35:
        status = "possible_affiliate"
    else:
        status = "not_found"

    return {
        "project_name": project_name,
        "query": query,
        "status": status,
        "confidence": best_score,
        "official_domain": official_domain,
        "official_url": official_url,
        "signup_url": signup_url,
        "signup_confidence": best_signup_score,
        "signup_terms": signup_terms,
        "affiliate_url": best_url,
        "matched_terms": best_terms,
        "candidates": candidates,
    }


async def research_affiliate_projects(project_names: list[str], max_results: int | None = None) -> dict:
    cleaned_names = _clean_project_names(project_names)
    requested_results = max_results or settings.AFFILIATE_RESEARCH_MAX_RESULTS
    report = {
        "id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "google_custom_search",
        "configured": bool(settings.GOOGLE_SEARCH_API_KEY and settings.GOOGLE_SEARCH_ENGINE_ID),
        "items": [],
        "summary": {
            "total": len(cleaned_names),
            "likely_affiliate": 0,
            "possible_affiliate": 0,
            "not_found": 0,
            "errors": 0,
        },
    }
    if not report["configured"]:
        report["error"] = "Google Search API is not configured. Add GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID to backend .env."
        return report

    async with httpx.AsyncClient(
        headers={"User-Agent": "AdsPulse Affiliate Research/1.0"},
        verify=certifi.where(),
    ) as client:
        for project_name in cleaned_names:
            try:
                item = await _research_one_project(client, project_name, requested_results)
            except httpx.HTTPStatusError as exc:
                detail = "Google Search API request failed."
                try:
                    detail = exc.response.json().get("error", {}).get("message", detail)
                except Exception:
                    pass
                item = {
                    "project_name": project_name,
                    "status": "error",
                    "confidence": 0,
                    "affiliate_url": None,
                    "matched_terms": [],
                    "candidates": [],
                    "error": detail,
                }
            except Exception as exc:
                item = {
                    "project_name": project_name,
                    "status": "error",
                    "confidence": 0,
                    "affiliate_url": None,
                    "matched_terms": [],
                    "candidates": [],
                    "error": str(exc),
                }
            report["items"].append(item)
            report["summary"][item["status"]] = report["summary"].get(item["status"], 0) + 1

    reports = _read_reports()
    reports.insert(0, report)
    _write_reports(reports[:100])
    return report


def affiliate_research_report_to_csv(report: dict) -> str:
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "project_name",
            "official_domain",
            "official_url",
            "signup_url",
            "signup_confidence",
            "status",
            "confidence",
            "affiliate_url",
            "matched_terms",
            "top_candidates",
        ],
    )
    writer.writeheader()
    for item in report.get("items", []):
        candidates = item.get("candidates", [])[:3]
        writer.writerow(
            {
                "project_name": item.get("project_name"),
                "official_domain": item.get("official_domain") or "",
                "official_url": item.get("official_url") or "",
                "signup_url": item.get("signup_url") or "",
                "signup_confidence": item.get("signup_confidence") or 0,
                "status": item.get("status"),
                "confidence": item.get("confidence"),
                "affiliate_url": item.get("affiliate_url") or "",
                "matched_terms": ", ".join(item.get("matched_terms", [])),
                "top_candidates": " | ".join(candidate.get("url", "") for candidate in candidates),
            }
        )
    return output.getvalue()


def list_affiliate_research_reports() -> list[dict]:
    return _read_reports()
