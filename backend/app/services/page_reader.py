"""HTTP-first page loading with an optional Playwright fallback."""

from dataclasses import dataclass

import httpx

from app.core.config import settings


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
}


@dataclass
class PageLoad:
    html: str = ""
    final_url: str = ""
    method: str = ""
    error: str = ""
    status_code: int | None = None


def _validate_html_response(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "")
    if response.status_code >= 400:
        raise httpx.HTTPStatusError(
            f"HTTP {response.status_code}",
            request=response.request,
            response=response,
        )
    if "html" not in content_type.lower():
        raise ValueError(f"Unsupported content type: {content_type or 'unknown'}")
    return response.text[: settings.PAGE_READER_MAX_HTML_CHARS]


def fetch_static_page(url: str) -> PageLoad:
    try:
        with httpx.Client(
            timeout=settings.PAGE_READER_HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers=DEFAULT_HEADERS,
        ) as client:
            response = client.get(url)
        return PageLoad(
            html=_validate_html_response(response),
            final_url=str(response.url),
            method="http",
            status_code=response.status_code,
        )
    except Exception as exc:
        return PageLoad(error=f"{type(exc).__name__}: {exc}", method="http")


async def fetch_static_page_async(client: httpx.AsyncClient, url: str) -> PageLoad:
    try:
        response = await client.get(
            url,
            follow_redirects=True,
            timeout=settings.PAGE_READER_HTTP_TIMEOUT_SECONDS,
            headers=DEFAULT_HEADERS,
        )
        return PageLoad(
            html=_validate_html_response(response),
            final_url=str(response.url),
            method="http",
            status_code=response.status_code,
        )
    except Exception as exc:
        return PageLoad(error=f"{type(exc).__name__}: {exc}", method="http")


def render_page(url: str) -> PageLoad:
    if not settings.ENABLE_HEADLESS_BROWSER:
        return PageLoad(method="playwright", error="Headless browser fallback is disabled.")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return PageLoad(
            method="playwright",
            error="Playwright is not installed. Run: pip install playwright && playwright install chromium",
        )

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=DEFAULT_HEADERS["User-Agent"],
                locale="en-US",
                ignore_https_errors=True,
                viewport={"width": 1440, "height": 1000},
            )
            page = context.new_page()

            def block_heavy_assets(route):
                if route.request.resource_type in {"image", "media", "font"}:
                    route.abort()
                else:
                    route.continue_()

            page.route("**/*", block_heavy_assets)
            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=settings.PAGE_READER_BROWSER_TIMEOUT_MS,
            )
            try:
                page.wait_for_load_state(
                    "networkidle",
                    timeout=min(4_000, settings.PAGE_READER_BROWSER_TIMEOUT_MS),
                )
            except Exception:
                pass
            page.wait_for_timeout(settings.PAGE_READER_SETTLE_MS)
            result = PageLoad(
                html=page.content()[: settings.PAGE_READER_MAX_HTML_CHARS],
                final_url=page.url,
                method="playwright",
                status_code=response.status if response else None,
            )
            context.close()
            browser.close()
            return result
    except Exception as exc:
        return PageLoad(method="playwright", error=f"{type(exc).__name__}: {exc}")


async def render_page_async(url: str) -> PageLoad:
    if not settings.ENABLE_HEADLESS_BROWSER:
        return PageLoad(method="playwright", error="Headless browser fallback is disabled.")
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return PageLoad(
            method="playwright",
            error="Playwright is not installed. Run: pip install playwright && playwright install chromium",
        )

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=DEFAULT_HEADERS["User-Agent"],
                locale="en-US",
                ignore_https_errors=True,
                viewport={"width": 1440, "height": 1000},
            )
            page = await context.new_page()

            async def block_heavy_assets(route):
                if route.request.resource_type in {"image", "media", "font"}:
                    await route.abort()
                else:
                    await route.continue_()

            await page.route("**/*", block_heavy_assets)
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=settings.PAGE_READER_BROWSER_TIMEOUT_MS,
            )
            try:
                await page.wait_for_load_state(
                    "networkidle",
                    timeout=min(4_000, settings.PAGE_READER_BROWSER_TIMEOUT_MS),
                )
            except Exception:
                pass
            await page.wait_for_timeout(settings.PAGE_READER_SETTLE_MS)
            result = PageLoad(
                html=(await page.content())[: settings.PAGE_READER_MAX_HTML_CHARS],
                final_url=page.url,
                method="playwright",
                status_code=response.status if response else None,
            )
            await context.close()
            await browser.close()
            return result
    except Exception as exc:
        return PageLoad(method="playwright", error=f"{type(exc).__name__}: {exc}")
