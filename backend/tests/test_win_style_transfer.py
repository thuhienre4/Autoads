import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from openai import APIConnectionError
from app.core.config import settings
from app.services.win_style_transfer import AdDraft, StyleProfile, draft_issues, target_facts, profile_fingerprint, _numbers
from app.services.win_templates import WinTemplateInput, _connect, delete_template, generate_from_template, save_template
from style_transfer_fixtures import PROFILE, BRIEF, PAGE, fake_client, valid_draft


class StyleTransferTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for key, value in [("WIN_TEMPLATE_STORE_PATH", str(Path(temp.name) / "win.db")), ("AI_PROVIDER", "openai"), ("OPENAI_API_KEY", "test-only")]:
            patcher = patch.object(settings, key, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.template = save_template(WinTemplateInput(name="Project A", headlines=["Save 40% With Acme", "Start Your Free Trial"], descriptions=["Explore Acme. Save 40% today. Start your Free Trial."], notes="Benefit first, short CTA"))

    def generate(self, client, brief=None, page=None):
        with patch("app.services.win_templates.OpenAI", return_value=client):
            return generate_from_template(self.template, BRIEF if brief is None else brief, PAGE if page is None else page)

    def test_old_project_is_absent_from_writer_and_reviewer_inputs(self):
        client = fake_client()
        result = self.generate(client)
        calls = client.chat.completions.create.call_args_list
        self.assertEqual(3, len(calls))
        for call in calls[1:]:
            reference = call.kwargs["messages"][1]["content"]
            self.assertNotIn("Acme", reference)
            self.assertNotIn("40%", reference)
            self.assertNotIn("Free Trial", reference)
            self.assertNotIn("source_names", reference)
        self.assertEqual("style-transfer-v2", result["template_applied"]["algorithm_version"])
        self.assertEqual(["F2"], result["template_applied"]["grounding"]["headlines"][0]["fact_ids"])
        self.assertEqual(BRIEF["landing_page_message"], result["template_applied"]["facts_used"][0]["text"])

    def test_profile_cache_reused_but_new_page_facts_are_not_cached(self):
        client = fake_client()
        first = self.generate(client)
        second_brief = {**BRIEF, "primary_offer": "Annual plans include onboarding"}
        second = self.generate(client, brief=second_brief)
        calls = client.chat.completions.create.call_args_list
        self.assertEqual(5, len(calls))
        self.assertFalse(first["template_applied"]["style_cached"])
        self.assertTrue(second["template_applied"]["style_cached"])
        self.assertIn("Annual plans include onboarding", calls[3].kwargs["messages"][1]["content"])
        self.assertNotEqual(profile_fingerprint(self.template, "a"), profile_fingerprint(self.template, "b"))
        self.assertNotEqual(profile_fingerprint(self.template, "a"), profile_fingerprint({**self.template, "notes": "Changed"}, "a"))
        delete_template(self.template["id"])
        with _connect() as db:
            self.assertEqual(0, db.execute("SELECT COUNT(*) FROM win_style_profiles").fetchone()[0])

    def test_source_brand_and_percentage_trigger_repair_before_review(self):
        bad = valid_draft()
        bad["headlines"][0]["text"] = "Save 40% With Acme"
        client = fake_client(drafts=[bad, valid_draft()])
        result = self.generate(client)
        self.assertEqual(2, result["template_applied"]["verification"]["attempts"])
        self.assertEqual(4, client.chat.completions.create.call_count)
        repair = json.loads(client.chat.completions.create.call_args_list[2].kwargs["messages"][1]["content"])
        self.assertTrue(any("source project" in issue for issue in repair["repair_feedback"]))
        self.assertTrue(any("numeric claim" in issue for issue in repair["repair_feedback"]))

    def test_semantic_review_repairs_unsupported_free_trial(self):
        bad = valid_draft()
        bad["headlines"][0]["text"] = "Start Your Free Trial"
        review = {"issues": [{"asset_type": "headlines", "index": 0, "reason": "Target facts do not offer a free trial."}]}
        result = self.generate(fake_client(drafts=[bad, valid_draft()], reviews=[review, {"issues": []}]))
        self.assertEqual(2, result["template_applied"]["verification"]["attempts"])
        self.assertNotIn("Start Your Free Trial", result["headlines"])

    def test_persistent_review_failure_never_returns_unreviewed_copy(self):
        issue = {"issues": [{"asset_type": "all", "index": 0, "reason": "Wrong product category and target language."}]}
        client = fake_client(reviews=[issue])
        with self.assertRaises(HTTPException) as error:
            self.generate(client)
        self.assertEqual(502, error.exception.status_code)
        self.assertEqual(5, client.chat.completions.create.call_count)

    def test_missing_target_details_does_not_call_ai(self):
        client = fake_client()
        with self.assertRaises(HTTPException) as error:
            self.generate(client, brief={"product_name": "NewCo", "target_keywords": ["free trial"]}, page={"fetched": False, "body_excerpt": "unusable response"})
        self.assertEqual(422, error.exception.status_code)
        client.chat.completions.create.assert_not_called()

    def test_manual_facts_supported_and_preferences_are_not_evidence(self):
        result = self.generate(fake_client(), brief={**BRIEF, "primary_cta": "Claim 90% Off"}, page={"fetched": False, "body_excerpt": "Old content 90% off"})
        self.assertEqual("manual_brief", result["template_applied"]["verification"]["source"])
        facts = target_facts({**BRIEF, "target_keywords": ["90% off"], "primary_cta": "Claim 90% Off"}, {"fetched": False, "body_excerpt": "90% off"})
        self.assertNotIn("90%", json.dumps(facts))

    def test_review_connection_error_never_falls_back_to_unchecked_copy(self):
        error = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))
        with self.assertRaises(HTTPException) as raised:
            self.generate(fake_client(reviews=[error]))
        self.assertEqual(502, raised.exception.status_code)

    def test_duplicate_invalid_evidence_and_wrong_units_are_rejected(self):
        raw = valid_draft()
        raw["headlines"][0]["text"] = "Organize Team Tasks!"
        raw["headlines"][2]["fact_ids"] = ["F404"]
        raw["headlines"][3] = {"text": "Save 30% Today", "fact_ids": ["F3"]}
        facts = target_facts({**BRIEF, "primary_offer": "30 days of support"}, {})
        issues = draft_issues(AdDraft.model_validate(raw), facts, StyleProfile.model_validate(PROFILE))
        self.assertTrue(any("too similar" in issue for issue in issues))
        self.assertTrue(any("invalid evidence" in issue for issue in issues))
        self.assertTrue(any("numeric claim" in issue for issue in issues))

    def test_source_brand_is_allowed_when_supported_by_new_brief(self):
        raw = valid_draft()
        raw["headlines"][0] = {"text": "Acme Integrations", "fact_ids": ["F3"]}
        facts = target_facts({**BRIEF, "primary_offer": "NewCo integrates with Acme"}, {})
        self.assertEqual([], draft_issues(AdDraft.model_validate(raw), facts, StyleProfile.model_validate(PROFILE)))

    def test_equivalent_numeric_units_are_accepted_without_confusing_percent(self):
        self.assertEqual(_numbers("30-Day Support"), _numbers("30 ngày"))
        self.assertEqual(_numbers("Plans from $29"), _numbers("Plans from 29 USD"))
        self.assertEqual(_numbers("Save 30 percent"), _numbers("Giảm 30%"))
        self.assertNotEqual(_numbers("Save 30%"), _numbers("30 days"))
