import copy
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

PROFILE = {"tone": "Trực tiếp, rõ ràng", "headline_patterns": ["{benefit} With {brand}", "{cta}"], "description_patterns": ["{feature}. {cta}."], "cta_style": "Động từ hành động ngắn ở cuối câu", "source_names": ["Acme"], "source_claims": ["Save 40%", "Free Trial"]}
HEADLINES = ["NewCo Project Tools", "Organize Team Tasks", "Track Project Progress", "Work Together Easily", "Explore Team Features", "Plan Work In One Place", "See Your Tasks Clearly", "Manage Team Projects", "Tools For Small Teams", "Keep Your Work Organized", "Discover NewCo", "Assign Tasks To Your Team", "View Project Updates", "Find Your Team Workflow", "Explore NewCo Features"]
DESCRIPTIONS = ["Organize team tasks and track project progress with NewCo. Explore features.", "Assign work to your team in one place. Discover NewCo project tools today.", "See project updates and keep tasks organized. Find tools for your small team.", "Plan projects together using NewCo. Learn about task management features."]
BRIEF = {"product_name": "NewCo", "landing_page_message": "NewCo helps small teams plan projects, assign tasks, track updates and organize work in one place.", "language": "English", "tone": "Professional", "target_audience": "small teams", "primary_cta": "Explore Features"}
PAGE = {"fetched": True, "title": "NewCo Project Tools", "meta_description": BRIEF["landing_page_message"], "body_excerpt": BRIEF["landing_page_message"], "headings": ["Organize team projects"], "error": ""}


def valid_draft():
    return {"headlines": [{"text": text, "fact_ids": ["F2"]} for text in HEADLINES], "descriptions": [{"text": text, "fact_ids": ["F2"]} for text in DESCRIPTIONS]}


def fake_client(drafts=None, reviews=None, profile=None):
    client = MagicMock()
    client.__enter__.return_value = client
    draft_values = iter(drafts or [valid_draft()])
    review_values = iter(reviews or [{"issues": []}])
    last = {"draft": valid_draft(), "review": {"issues": []}}
    def respond(**kwargs):
        name = kwargs["response_format"]["json_schema"]["name"]
        if name == "win_style":
            data = profile if profile is not None else PROFILE
        elif name == "win_ads_grounded":
            data = next(draft_values, last["draft"])
            last["draft"] = data
        elif name == "win_ads_review":
            data = next(review_values, last["review"])
            last["review"] = data
        else:
            raise AssertionError(name)
        if isinstance(data, Exception):
            raise data
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(refusal=None, content=json.dumps(copy.deepcopy(data))))])
    client.chat.completions.create.side_effect = respond
    return client
