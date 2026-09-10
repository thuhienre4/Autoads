"""Persistent RSA examples and generation grounded in a selected example."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings
from app.services.win_style_transfer import (
    ALGORITHM_VERSION, StyleProfile, InvalidModelOutput, extract_style,
    profile_fingerprint, target_facts, write_and_review,
)


class WinTemplateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    notes: str = Field(default="", max_length=2000)
    headlines: list[str] = Field(min_length=1, max_length=15)
    descriptions: list[str] = Field(min_length=1, max_length=4)

    @field_validator("headlines", "descriptions")
    @classmethod
    def validate_assets(cls, values, info):
        limit = 30 if info.field_name == "headlines" else 90
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > limit or "\n" in value or "\r" in value or value.startswith("=") for value in cleaned):
            raise ValueError(f"{info.field_name}: mỗi dòng phải có 1–{limit} ký tự.")
        if len({value.casefold() for value in cleaned}) != len(cleaned):
            raise ValueError(f"{info.field_name}: có nội dung trùng lặp.")
        return cleaned


@contextmanager
def _connect():
    root = Path(settings.RAILWAY_VOLUME_MOUNT_PATH) if settings.RAILWAY_VOLUME_MOUNT_PATH else Path(__file__).resolve().parents[2] / "data"
    path = Path(settings.WIN_TEMPLATE_STORE_PATH) if settings.WIN_TEMPLATE_STORE_PATH else root / "win_templates.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    try:
        with db:
            db.execute("CREATE TABLE IF NOT EXISTS win_templates (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, data TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS win_style_profiles (template_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, data TEXT NOT NULL)")
            yield db
    finally:
        db.close()


def list_templates():
    with _connect() as db:
        rows = db.execute("SELECT id, created_at, data FROM win_templates ORDER BY created_at DESC").fetchall()
    return [{"id": key, "created_at": created, **json.loads(data)} for key, created, data in rows]


def save_template(payload: WinTemplateInput):
    return save_templates([payload])[0]


def save_templates(payloads: list[WinTemplateInput]):
    records = [{"id": uuid4().hex, "created_at": datetime.now(timezone.utc).isoformat(), **payload.model_dump()} for payload in payloads]
    with _connect() as db:
        db.executemany("INSERT INTO win_templates VALUES (?, ?, ?)", [(record["id"], record["created_at"], payload.model_dump_json()) for record, payload in zip(records, payloads)])
    return records


def get_template(template_id):
    with _connect() as db:
        row = db.execute("SELECT data FROM win_templates WHERE id = ?", (template_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Mẫu content win không còn tồn tại. Hãy chọn lại mẫu.")
    return {"id": template_id, **json.loads(row[0])}


def delete_template(template_id):
    with _connect() as db:
        removed = db.execute("DELETE FROM win_templates WHERE id = ?", (template_id,)).rowcount
        db.execute("DELETE FROM win_style_profiles WHERE template_id = ?", (template_id,))
    if not removed:
        raise HTTPException(404, "Không tìm thấy mẫu content win.")
    return {"deleted": template_id}


def _style_profile(client, template):
    fingerprint = profile_fingerprint(template, settings.OPENAI_MODEL)
    with _connect() as db:
        row = db.execute("SELECT data FROM win_style_profiles WHERE template_id = ? AND fingerprint = ?", (template["id"], fingerprint)).fetchone()
    if row:
        try:
            return StyleProfile.model_validate_json(row[0]), True
        except ValueError:
            pass  # Rebuild invalid cache data from the unchanged original example.
    profile = extract_style(client, settings.OPENAI_MODEL, template)
    with _connect() as db:
        db.execute(
            "INSERT OR REPLACE INTO win_style_profiles (template_id, fingerprint, data) SELECT ?, ?, ? WHERE EXISTS (SELECT 1 FROM win_templates WHERE id = ?)",
            (template["id"], fingerprint, profile.model_dump_json(), template["id"]),
        )
    return profile, False


def generate_from_template(template, brief, page_context):
    if settings.AI_PROVIDER.casefold() != "openai" or not settings.OPENAI_API_KEY:
        raise HTTPException(503, "Viết theo content win cần cấu hình AI_PROVIDER=openai và OPENAI_API_KEY trên máy chủ.")
    facts = target_facts(brief, page_context)
    if not facts or all(fact["source"] == "brief.product_name" for fact in facts):
        raise HTTPException(422, "Chưa đủ thông tin của dự án mới để viết theo mẫu. Hãy kiểm tra landing page hoặc nhập mô tả sản phẩm, lợi ích và ưu đãi thực tế.")
    try:
        with OpenAI(api_key=settings.OPENAI_API_KEY, timeout=45, max_retries=0) as client:
            profile, cached = _style_profile(client, template)
            draft, attempts, style = write_and_review(client, settings.OPENAI_MODEL, template, brief, facts, profile)
    except OpenAIError as exc:
        raise HTTPException(502, "Không hoàn tất được bước phân tích/viết/kiểm tra AI. Hãy kiểm tra cấu hình hoặc thử lại.") from exc
    except (InvalidModelOutput, ValueError, KeyError, IndexError, TypeError) as exc:
        raise HTTPException(502, "AI chưa tạo được bộ quảng cáo đạt kiểm tra nội dung và giới hạn ký tự. Hãy bổ sung thông tin dự án hoặc thử lại.") from exc
    has_page = any(fact["source"].startswith("landing_page.") for fact in facts)
    return {
        "headlines": [asset.text for asset in draft.headlines],
        "descriptions": [asset.text for asset in draft.descriptions],
        "template_applied": {
            "id": template["id"], "name": template["name"],
            "algorithm_version": ALGORITHM_VERSION,
            "style_cached": cached,
            "style_notes": [f"Giọng văn: {style['tone']}", f"Cách dùng CTA: {style['cta_style']}", "Áp dụng nhịp câu và thứ tự trình bày của mẫu cho thông tin dự án mới."],
            "verification": {"status": "reviewed", "attempts": attempts, "source": "landing_page_and_brief" if has_page else "manual_brief"},
            "facts_used": [fact for fact in facts if any(fact["id"] in asset.fact_ids for asset in [*draft.headlines, *draft.descriptions])],
            "grounding": {key: [{"text": asset.text, "fact_ids": asset.fact_ids} for asset in getattr(draft, key)] for key in ("headlines", "descriptions")},
        },
    }
