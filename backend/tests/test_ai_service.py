import re
import unittest
from unittest.mock import patch

from app.schemas.ads import AdGenerationRequest
from app.services.ai_service import LandingPageHTMLParser, generate_google_ads_copy


PAGE_CONTEXT = {
    "source_url": "https://example.com/plugins",
    "final_url": "https://example.com/plugins",
    "fetched": True,
    "title": "Premium WordPress Plugins for WooCommerce",
    "meta_description": "WordPress plugins and WooCommerce extensions with fast setup and support.",
    "headings": ["Build a better WooCommerce store", "Trusted WordPress plugin support"],
    "body_excerpt": "Compare WordPress plugin features, pricing, support and customer benefits.",
    "error": "",
}


class GenerateGoogleAdsCopyTests(unittest.TestCase):
    def request(self, **overrides):
        values = {
            "product_name": "Premium WordPress Plugins",
            "website": "https://example.com/plugins",
            "landing_page_url": "https://example.com/plugins",
            "language": "English",
            "tone": "Professional",
            "target_audience": "WooCommerce store owners",
            "landing_page_message": "Plugins built for faster stores",
            "primary_offer": "30-day money-back guarantee",
            "primary_cta": "Get The Plugin",
            "trust_signals": "expert support and fast setup",
            "target_keywords": ["wordpress plugin", "woocommerce extensions", "plugin pricing"],
        }
        values.update(overrides)
        return AdGenerationRequest(**values)

    @patch("app.services.ai_service._fetch_landing_page_context", return_value=PAGE_CONTEXT)
    def test_generates_complete_rsa_with_valid_limits(self, _fetch):
        result = generate_google_ads_copy(self.request())

        self.assertEqual(15, len(result["headlines"]))
        self.assertEqual(4, len(result["descriptions"]))
        self.assertTrue(all(len(item) <= 30 for item in result["headlines"]))
        self.assertTrue(all(len(item) <= 90 for item in result["descriptions"]))
        self.assertFalse(any("aligned with" in item.casefold() for item in result["descriptions"]))
        self.assertFalse(any("matched to" in item.casefold() for item in result["descriptions"]))
        self.assertEqual(len(result["headlines"]), len({item.casefold() for item in result["headlines"]}))
        self.assertIn("Wordpress Plugin", result["headlines"])
        self.assertNotIn("Best Wordpress Plugin", result["headlines"])
        self.assertNotIn("Proven, Measurable Results", result["headlines"])

    @patch("app.services.ai_service._fetch_landing_page_context", return_value=PAGE_CONTEXT)
    def test_headlines_use_page_facts_and_flag_unsupported_keywords(self, _fetch):
        result = generate_google_ads_copy(self.request(
            target_keywords=["wordpress plugin", "unrelated crypto hosting"],
        ))
        alignment = result["landing_page_alignment"]["headline_alignment"]
        self.assertIn("wordpress plugin", alignment["page_supported_keywords"])
        self.assertIn("unrelated crypto hosting", alignment["unsupported_keywords"])
        self.assertTrue(alignment["page_facts_used"])
        self.assertFalse(any("Best " in item or "Proven" in item for item in result["headlines"]))

    @patch("app.services.ai_service._fetch_landing_page_context", return_value=PAGE_CONTEXT)
    def test_returns_actionable_seo_diagnostics(self, _fetch):
        result = generate_google_ads_copy(self.request())
        seo = result["seo_analysis"]

        self.assertGreaterEqual(seo["score"], 70)
        self.assertEqual("wordpress plugin", seo["primary_keyword"])
        self.assertEqual("transactional", seo["search_intent"])
        self.assertGreater(seo["headline_keyword_coverage"], 0)
        self.assertGreaterEqual(seo["landing_page_keyword_coverage"], 60)
        self.assertIn("landing_page", seo["subscores"])
        self.assertIn("rsa_quality", seo["subscores"])
        self.assertGreaterEqual(seo["potential_score"], seo["score"])
        self.assertTrue(seo["improvement_plan"])
        self.assertTrue(any(check["label"] == "All RSA limits valid" and check["passed"] for check in seo["checks"]))

    @patch("app.services.ai_service._fetch_landing_page_context", return_value=PAGE_CONTEXT)
    def test_extracts_keywords_when_user_does_not_supply_them(self, _fetch):
        result = generate_google_ads_copy(self.request(product_name="", target_keywords=[]))

        self.assertTrue(result["landing_page_alignment"]["keywords_used"])
        self.assertEqual("premium wordpress plugins", result["landing_page_alignment"]["keywords_used"][0])
        self.assertEqual("landing_page", result["landing_page_alignment"]["content_source"])
        self.assertEqual("Professional", result["landing_page_alignment"]["tone"])
        self.assertTrue(result["seo_analysis"]["primary_keyword"])

    @patch("app.services.ai_service._fetch_landing_page_context")
    def test_normalizes_capitalization_and_excludes_coupon_codes(self, fetch):
        fetch.return_value = {
            **PAGE_CONTEXT,
            "title": "Planet Beauty Coupons and Promo Codes",
            "headings": [
                "Planet Beauty Coupon Code TINA20 - 20% OFF",
                "Planet Beauty Coupon Code WEB20 - 20% OFF",
                "Today's Best Planet Beauty Offers",
                "All Verified Planet Beauty Coupons",
            ],
            "content_phrases": [
                "Browse verified Planet Beauty coupons and current beauty offers.",
                "Compare available savings before visiting the merchant.",
            ],
        }

        result = generate_google_ads_copy(self.request(
            product_name="",
            target_keywords=[],
            primary_offer="",
            trust_signals="",
        ))
        assets = [*result["headlines"], *result["descriptions"]]

        self.assertFalse(any(re.search(r"\b[A-Z]{2,}\d+\b", item) for item in assets))
        self.assertFalse(any(re.search(r"\bOFF\b", item) for item in assets))
        self.assertGreaterEqual(len(result["headlines"]), 3)
        self.assertGreaterEqual(len(result["descriptions"]), 2)

    @patch("app.services.ai_service._fetch_landing_page_context")
    def test_uses_detected_offer_cta_and_trust_when_fields_are_empty(self, fetch):
        fetch.return_value = {
            **PAGE_CONTEXT,
            "detected_offers": ["Start a free 14-day trial."],
            "detected_ctas": ["Start Free Trial"],
            "detected_trust_signals": ["Trusted by 2,000 customers."],
        }
        result = generate_google_ads_copy(self.request(
            primary_offer="",
            primary_cta="",
            trust_signals="",
        ))

        alignment = result["landing_page_alignment"]
        self.assertIn("14-day trial", alignment["offer_used"])
        self.assertEqual("Start Free Trial", result["cta_suggestions"][0])
        self.assertIn("2,000 customers", alignment["trust_used"])


class LandingPageHTMLParserTests(unittest.TestCase):
    def test_prefers_main_content_and_preserves_nested_heading_text(self):
        parser = LandingPageHTMLParser()
        parser.feed("""
            <html><head><title>Actual Product | Brand</title>
            <meta property="og:description" content="The exact product description."></head>
            <body><nav><a>Unrelated navigation offer</a></nav>
            <main><h1>Build <span>Better Stores</span></h1>
            <p>Actual landing page content describing the product, its useful features, customer benefits,
            transparent pricing, fast setup, integrations, and expert support for online store owners.</p></main>
            <footer><p>Privacy Terms Careers Cookie Settings</p></footer></body></html>
        """)
        result = parser.summary()

        self.assertEqual("Actual Product | Brand", result["title"])
        self.assertEqual("The exact product description.", result["meta_description"])
        self.assertEqual("Build Better Stores", result["headings"][0])
        self.assertIn("Actual landing page content", result["body_excerpt"])
        self.assertNotIn("navigation", result["body_excerpt"])
        self.assertNotIn("Privacy", result["body_excerpt"])

    def test_filters_popup_noise_and_extracts_conversion_signals(self):
        parser = LandingPageHTMLParser()
        parser.feed("""
            <html><head><title>Analytics Platform</title>
            <meta name="description" content="Understand performance with accurate analytics."></head>
            <body>
              <div class="cookie-consent popup"><p>Accept cookies and subscribe to our newsletter.</p></div>
              <main>
                <h1>Analytics built for growing teams</h1>
                <p>Start a free 14-day trial with no credit card required.</p>
                <p>Trusted by more than 2,000 customers with expert support.</p>
                <a href="/trial"><span>Start Free Trial</span></a>
                <p>Monitor acquisition, revenue, and conversion performance in one workspace
                with reliable reports for marketing and leadership teams.</p>
              </main>
            </body></html>
        """)
        result = parser.summary()

        self.assertNotIn("Accept cookies", result["body_excerpt"])
        self.assertIn("Start Free Trial", result["detected_ctas"])
        self.assertTrue(any("14-day trial" in item for item in result["detected_offers"]))
        self.assertTrue(any("2,000 customers" in item for item in result["detected_trust_signals"]))
        self.assertGreater(result["word_count"], 20)
        self.assertGreaterEqual(result["extraction_confidence"], 60)

    def test_extracts_structured_product_and_semantic_facts(self):
        parser = LandingPageHTMLParser()
        parser.feed("""
            <html><head>
              <title>Generic Store Title</title>
              <script type="application/ld+json">
                {
                  "@context": "https://schema.org",
                  "@type": "Product",
                  "name": "Precision Analytics Pro",
                  "brand": {"@type": "Brand", "name": "Northstar"},
                  "description": "Revenue analytics for performance marketing teams.",
                  "offers": {"@type": "Offer", "price": "49", "priceCurrency": "USD"},
                  "aggregateRating": {"ratingValue": "4.8", "reviewCount": "312"}
                }
              </script>
            </head><body><main>
              <h1>Know which campaigns drive revenue</h1>
              <ul><li>Automated attribution reports with channel-level tracking.</li></ul>
              <p>Reduce manual reporting and make faster budget decisions.</p>
              <a href="/demo">Book a Demo</a>
            </main></body></html>
        """)
        result = parser.summary()

        self.assertEqual("Precision Analytics Pro", result["structured_data"]["product_name"])
        self.assertEqual("Northstar", result["structured_data"]["brand"])
        self.assertEqual("49", result["structured_data"]["price"])
        self.assertTrue(any("Automated attribution" in item for item in result["key_features"]))
        self.assertTrue(any("Reduce manual reporting" in item for item in result["customer_benefits"]))
        self.assertTrue(result["key_facts"])

    def test_ignores_malformed_json_ld_without_losing_page_content(self):
        parser = LandingPageHTMLParser()
        parser.feed("""
            <html><head><script type="application/ld+json">{not valid}</script></head>
            <body><main><h1>Reliable campaign reporting</h1>
            <p>Automated reporting helps teams save time and improve decisions.</p></main></body></html>
        """)
        result = parser.summary()

        self.assertEqual({}, result["structured_data"])
        self.assertIn("Reliable campaign reporting", result["body_excerpt"])


if __name__ == "__main__":
    unittest.main()
