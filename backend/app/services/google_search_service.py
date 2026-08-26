import httpx
import certifi
import urllib3
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse

from app.core.config import settings


GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
DUCKDUCKGO_SEARCH_URL = "https://duckduckgo.com/html/"


class DuckDuckGoResultParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self._current = None
        self._in_result_link = False
        self._in_snippet = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        class_name = attrs_dict.get("class", "")
        if tag == "a" and "result__a" in class_name:
            self._current = {"title": "", "url": _clean_duckduckgo_url(attrs_dict.get("href", "")), "snippet": ""}
            self._in_result_link = True
        elif tag in {"a", "div"} and self._current and "result__snippet" in class_name:
            self._in_snippet = True

    def handle_endtag(self, tag):
        if tag == "a" and self._in_result_link:
            self._in_result_link = False
            if self._current and self._current["title"] and self._current["url"]:
                self.results.append(self._current)
            self._current = None
        elif tag in {"a", "div"} and self._in_snippet:
            self._in_snippet = False

    def handle_data(self, data):
        if not self._current:
            return
        text = " ".join(data.split())
        if not text:
            return
        if self._in_result_link:
            self._current["title"] = f"{self._current['title']} {text}".strip()
        elif self._in_snippet:
            self._current["snippet"] = f"{self._current['snippet']} {text}".strip()


def _clean_duckduckgo_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.path.startswith("/l/"):
        redirect_url = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(redirect_url) if redirect_url else url
    return url


def google_search_configured() -> bool:
    return bool(settings.GOOGLE_SEARCH_API_KEY and settings.GOOGLE_SEARCH_ENGINE_ID)


async def fallback_web_search(query: str, max_results: int = 10) -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AI Google Ads Optimizer/1.0)"}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, verify=certifi.where()) as client:
        response = await client.get(
            DUCKDUCKGO_SEARCH_URL,
            params={"q": query},
            timeout=8,
        )
        response.raise_for_status()
    parser = DuckDuckGoResultParser()
    parser.feed(response.text)
    items = parser.results[: max(1, min(max_results, 10))]
    return {
        "query": query,
        "configured": True,
        "source": "duckduckgo_fallback",
        "total_results": None,
        "items": [
            {
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "display_url": urlparse(item.get("url") or "").hostname or "",
                "snippet": item.get("snippet") or "",
            }
            for item in items
        ],
    }


async def search_google(query: str, max_results: int = 10) -> dict:
    if not google_search_configured():
        raise RuntimeError("Missing GOOGLE_SEARCH_API_KEY or GOOGLE_SEARCH_ENGINE_ID in backend .env")

    params = {
        "key": settings.GOOGLE_SEARCH_API_KEY,
        "cx": settings.GOOGLE_SEARCH_ENGINE_ID,
        "q": query,
        "num": max(1, min(max_results, 10)),
    }
    headers = {"User-Agent": "AI Google Ads Optimizer/1.0"}
    try:
        async with httpx.AsyncClient(headers=headers, verify=certifi.where()) as client:
            response = await client.get(GOOGLE_SEARCH_URL, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
    except httpx.ConnectError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        async with httpx.AsyncClient(headers=headers, verify=False) as client:
            response = await client.get(GOOGLE_SEARCH_URL, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("error", {}).get("message", "")
        except Exception:
            pass
        if exc.response.status_code == 403 and "Custom Search JSON API" in detail:
            return await fallback_web_search(query, max_results=max_results)
        raise

    return {
        "query": query,
        "configured": True,
        "source": "google_custom_search",
        "total_results": payload.get("searchInformation", {}).get("totalResults"),
        "items": [
            {
                "title": item.get("title") or "",
                "url": item.get("link") or "",
                "display_url": item.get("displayLink") or "",
                "snippet": item.get("snippet") or "",
            }
            for item in payload.get("items", []) or []
        ],
    }
