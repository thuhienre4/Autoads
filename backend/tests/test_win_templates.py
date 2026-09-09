import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.ai import router
from app.core.config import settings
from app.schemas.ads import AdGenerationRequest
from app.services.ai_service import generate_google_ads_copy
from app.services.win_templates import WinTemplateInput, generate_from_template, save_template
from test_ai_service import PAGE_CONTEXT


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

    def mock_ai(self, assets):
        client = MagicMock()
        client.__enter__.return_value = client
        client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(refusal=None, content=json.dumps(assets)))])
        return client

    @patch.object(settings, "AI_PROVIDER", "openai")
    @patch.object(settings, "OPENAI_API_KEY", "test-only")
    def test_selected_template_reaches_ai_and_replaces_rule_assets(self):
        record = save_template(WinTemplateInput(**self.payload))
        assets = {"headlines": [f"Better Workflow {i}" for i in range(15)], "descriptions": [f"Organize your team with NewCo. Explore features {i}." for i in range(4)], "style_notes": ["Mở đầu bằng lợi ích.", "CTA ngắn gọn."]}
        client = self.mock_ai(assets)
        with patch("app.services.win_templates.OpenAI", return_value=client), patch("app.services.ai_service._cached_landing_page_context", return_value=PAGE_CONTEXT):
            result = generate_google_ads_copy(AdGenerationRequest(website="https://example.com", landing_page_url="https://example.com", product_name="NewCo", win_template_id=record["id"]))
        self.assertEqual(result["headlines"], assets["headlines"])
        self.assertEqual(result["template_applied"]["id"], record["id"])
        reference = json.loads(client.chat.completions.create.call_args.kwargs["messages"][1]["content"])
        self.assertEqual(reference["example"]["headlines"], self.payload["headlines"])
        self.assertEqual(reference["new_brief"]["product_name"], "NewCo")

    @patch.object(settings, "AI_PROVIDER", "openai")
    @patch.object(settings, "OPENAI_API_KEY", "test-only")
    def test_invalid_ai_output_is_not_silently_truncated(self):
        record = save_template(WinTemplateInput(**self.payload))
        with patch("app.services.win_templates.OpenAI", return_value=self.mock_ai({"headlines": ["x" * 31], "descriptions": ["Test"], "style_notes": []})), patch("app.services.ai_service._cached_landing_page_context", return_value=PAGE_CONTEXT):
            result = self.client.post("/generate-ads", json={"website": "https://example.com", "landing_page_url": "https://example.com", "win_template_id": record["id"]})
        self.assertEqual(result.status_code, 502)

    @patch.object(settings, "OPENAI_API_KEY", None)
    def test_missing_configuration_is_explicit(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as error:
            generate_from_template({}, {}, {})
        self.assertEqual(error.exception.status_code, 503)
