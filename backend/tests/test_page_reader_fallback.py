import unittest
from unittest.mock import AsyncMock, patch

from app.services.ai_service import _fetch_landing_page_context
from app.services.affiliate_research_service import TextExtractor, _read_page_text
from app.services.page_reader import PageLoad


RICH_HTML = """
<html>
  <head><title>Rendered Analytics Platform</title></head>
  <body><main>
    <h1>Analytics for growing teams</h1>
    <p>{body}</p>
  </main></body>
</html>
""".format(body=" ".join(["Reliable acquisition and conversion reporting."] * 100))


class LandingPageBrowserFallbackTests(unittest.TestCase):
    @patch("app.services.ai_service.render_page")
    @patch("app.services.ai_service.fetch_static_page")
    def test_keeps_http_for_a_complete_static_page(self, static_fetch, render):
        static_fetch.return_value = PageLoad(
            html=RICH_HTML,
            final_url="https://example.com/",
            method="http",
        )

        result = _fetch_landing_page_context("https://example.com/")

        self.assertTrue(result["fetched"])
        self.assertEqual("http", result["fetch_method"])
        self.assertFalse(result["browser_fallback_used"])
        render.assert_not_called()

    @patch("app.services.ai_service.render_page")
    @patch("app.services.ai_service.fetch_static_page")
    def test_renders_javascript_shell_with_playwright(self, static_fetch, render):
        static_fetch.return_value = PageLoad(
            html="<html><head><title>Loading</title></head><body><div id='root'></div></body></html>",
            final_url="https://example.com/app",
            method="http",
        )
        render.return_value = PageLoad(
            html=RICH_HTML,
            final_url="https://example.com/app",
            method="playwright",
        )

        result = _fetch_landing_page_context("https://example.com/app")

        self.assertTrue(result["fetched"])
        self.assertEqual("playwright", result["fetch_method"])
        self.assertTrue(result["browser_fallback_used"])
        self.assertGreater(result["word_count"], 80)

    @patch("app.services.ai_service.render_page")
    @patch("app.services.ai_service.fetch_static_page")
    def test_reports_both_failures_without_crashing(self, static_fetch, render):
        static_fetch.return_value = PageLoad(method="http", error="HTTP timeout")
        render.return_value = PageLoad(method="playwright", error="Browser timeout")

        result = _fetch_landing_page_context("https://example.com/")

        self.assertFalse(result["fetched"])
        self.assertEqual("HTTP timeout", result["http_error"])
        self.assertEqual("Browser timeout", result["error"])


class AffiliateRenderedContentTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_rendered_text_when_static_html_is_sparse(self):
        with (
            patch(
                "app.services.affiliate_research_service._fetch_page_text",
                new=AsyncMock(return_value="Loading"),
            ),
            patch(
                "app.services.affiliate_research_service.render_page_async",
                new=AsyncMock(
                    return_value=PageLoad(
                        html="<main><h1>Affiliate Program</h1><p>Earn commission. Sign up today.</p></main>",
                        final_url="https://example.com/affiliate",
                        method="playwright",
                    )
                ),
            ),
        ):
            text, method, error = await _read_page_text(object(), "https://example.com/affiliate")

        self.assertIn("Affiliate Program", text)
        self.assertEqual("playwright", method)
        self.assertEqual("", error)

    def test_text_extractor_recovers_after_nested_skipped_content(self):
        extractor = TextExtractor()
        extractor.feed(
            "<main>Visible<script><span>Hidden</span></script>"
            "<svg><path></path></svg><p>Affiliate commission</p></main>"
        )

        self.assertIn("Visible", extractor.text())
        self.assertIn("Affiliate commission", extractor.text())
        self.assertNotIn("Hidden", extractor.text())


if __name__ == "__main__":
    unittest.main()
