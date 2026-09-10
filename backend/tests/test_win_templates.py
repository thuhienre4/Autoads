import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.ai import router
from app.core.config import settings
from app.schemas.ads import AdGenerationRequest
from app.services.ai_service import generate_google_ads_copy
from app.services.win_templates import WinTemplateInput, generate_from_template, save_template
from test_ai_service import PAGE_CONTEXT
from style_transfer_fixtures import fake_client, HEADLINES, BRIEF, PAGE


class WinTemplateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = patch.object(settings, "WIN_TEMPLATE_STORE_PATH", str(Path(self.tmp.name) / "templates.db"))
        self.store.start()
        self.addCleanup(self.store.stop)
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.payload = {"name": "Benefit first", "headlines": ["Work Smarter"], "descriptions": ["Organize work in one place. Explore Acme today."], "notes": "Short CTA"}

    def test_create_reload_delete_and_missing_selection(self):
        result = self.client.post("/win-templates", json=self.payload)
        self.assertEqual(result.status_code, 201)
        record = result.json()
        self.assertEqual(self.client.get("/win-templates").json()["templates"], [record])
        self.assertEqual(self.client.delete(f'/win-templates/{record["id"]}').status_code, 200)
        self.assertEqual(self.client.get("/win-templates").json()["templates"], [])
        response = self.client.post("/generate-ads", json={"website": "https://example.com", "landing_page_url": "https://example.com", "win_template_id": record["id"]})
        self.assertEqual(response.status_code, 404)

    def test_reject_invalid_assets_without_saving(self):
        for changes in ({"headlines": ["x" * 31]}, {"headlines": [" "]}, {"headlines": ["Same", "same"]}, {"descriptions": []}, {"descriptions": ["a\nb"]}):
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post("/win-templates", json={**self.payload, **changes}).status_code, 422)
        self.assertEqual(self.client.get("/win-templates").json()["templates"], [])

    @patch.object(settings, "AI_PROVIDER", "openai")
    @patch.object(settings, "OPENAI_API_KEY", "test-only")
    def test_selected_template_reaches_ai_and_replaces_rule_assets(self):
        record = save_template(WinTemplateInput(**self.payload))
        client = fake_client()
        with patch("app.services.win_templates.OpenAI", return_value=client), patch("app.services.ai_service._cached_landing_page_context", return_value=PAGE):
            result = generate_google_ads_copy(AdGenerationRequest(website="https://example.com", landing_page_url="https://example.com", win_template_id=record["id"], **BRIEF))
        self.assertEqual(result["headlines"], HEADLINES)
        self.assertEqual(result["template_applied"]["id"], record["id"])
        calls = client.chat.completions.create.call_args_list
        self.assertEqual(json.loads(calls[0].kwargs["messages"][1]["content"])["headlines"], self.payload["headlines"])
        reference = json.loads(calls[1].kwargs["messages"][1]["content"])
        self.assertEqual(reference["target_facts"][0]["text"], "NewCo")
        self.assertNotIn("example", reference)
        self.assertEqual("reviewed", result["template_applied"]["verification"]["status"])

    @patch.object(settings, "AI_PROVIDER", "openai")
    @patch.object(settings, "OPENAI_API_KEY", "test-only")
    def test_invalid_ai_output_is_not_silently_truncated(self):
        record = save_template(WinTemplateInput(**self.payload))
        with patch("app.services.win_templates.OpenAI", return_value=fake_client(drafts=[{"headlines": [], "descriptions": []}])), patch("app.services.ai_service._cached_landing_page_context", return_value=PAGE_CONTEXT):
            result = self.client.post("/generate-ads", json={"website": "https://example.com", "landing_page_url": "https://example.com", "win_template_id": record["id"]})
        self.assertEqual(result.status_code, 502)

    @patch.object(settings, "OPENAI_API_KEY", None)
    def test_missing_configuration_is_explicit(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as error:
            generate_from_template({}, {}, {})
        self.assertEqual(error.exception.status_code, 503)
