import json
import csv
from io import StringIO
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
HISTORY_FILE = DATA_DIR / "publish_history.json"


def _json_value(value):
    """Keep Decimal-like monetary values numeric in history snapshots."""
    if hasattr(value, "as_integer_ratio"):
        return int(value) if value == int(value) else float(value)
    return str(value)


def _read_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        rows = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return rows if isinstance(rows, list) else [rows]
    except (json.JSONDecodeError, OSError):
        return []


def _write_history(rows: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def record_publish_history(payload, plan: dict, result: dict, mode: str, status: str) -> dict:
    rows = _read_history()
    plan_snapshot = json.loads(json.dumps(plan, ensure_ascii=False, default=_json_value))
    result_snapshot = json.loads(json.dumps(result, ensure_ascii=False, default=_json_value))
    record = {
        "id": uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "status": status,
        "customer_ids": result.get("customer_ids") or plan.get("customer_ids") or [],
        "campaign_name": payload.campaign_name,
        "landing_page_url": str(payload.landing_page_url),
        "target_location": payload.target_location,
        "enable_immediately": bool(getattr(payload, "enable_immediately", False)),
        "schedule": {
            "enabled": bool(getattr(payload, "schedule_enabled", False)),
            "scheduled_at": getattr(payload, "scheduled_at", None),
            "timezone": getattr(payload, "schedule_timezone", None),
        },
        "budget": {
            "daily_budget_vnd": _json_value(payload.daily_budget_vnd),
            "manual_cpc_bid_vnd": _json_value(payload.manual_cpc_bid_vnd),
            "currency_code": getattr(payload, "currency_code", "VND"),
        },
        "content": {
            "keywords": payload.keywords,
            "headlines": payload.headlines[:15],
            "descriptions": payload.descriptions[:4],
        },
        "plan": plan_snapshot,
        "result": result_snapshot,
        "metrics": {
            "clicks": 0,
            "impressions": 0,
            "cost": 0,
            "conversions": 0,
            "conversion_value": 0,
        },
    }
    rows.insert(0, record)
    _write_history(rows[:500])
    return record


def list_publish_history(customer_id: str | None = None, limit: int = 100) -> list[dict]:
    rows = _read_history()
    if customer_id:
        rows = [row for row in rows if customer_id in (row.get("customer_ids") or [])]
    return rows[:limit]


def list_due_scheduled_history(now: datetime | None = None, limit: int = 25) -> list[dict]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    due_rows = []
    for row in _read_history():
        schedule = row.get("schedule") or {}
        if row.get("status") != "scheduled" or row.get("mode") != "scheduled":
            continue
        if not schedule.get("enabled"):
            continue
        scheduled_at = _parse_datetime(schedule.get("scheduled_at"))
        if scheduled_at and scheduled_at <= now:
            due_rows.append(row)
    return due_rows[:limit]


def update_publish_history_record(record_id: str, patch: dict) -> dict | None:
    rows = _read_history()
    updated = None
    for row in rows:
        if row.get("id") != record_id:
            continue
        row.update(patch)
        updated = row
        break
    if updated:
        _write_history(rows[:500])
    return updated


def export_publish_history_csv(customer_id: str | None = None) -> str:
    rows = list_publish_history(customer_id=customer_id, limit=500)
    output = StringIO()
    fieldnames = [
        "created_at",
        "mode",
        "status",
        "customer_ids",
        "campaign_name",
        "landing_page_url",
        "target_location",
        "scheduled_at",
        "schedule_timezone",
        "currency_code",
        "daily_budget_vnd",
        "manual_cpc_bid_vnd",
        "keywords",
        "headlines",
        "descriptions",
        "clicks",
        "impressions",
        "cost",
        "conversions",
        "conversion_value",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        content = row.get("content") or {}
        budget = row.get("budget") or {}
        metrics = row.get("metrics") or {}
        schedule = row.get("schedule") or {}
        writer.writerow(
            {
                "created_at": row.get("created_at", ""),
                "mode": row.get("mode", ""),
                "status": row.get("status", ""),
                "customer_ids": ", ".join(row.get("customer_ids") or []),
                "campaign_name": row.get("campaign_name", ""),
                "landing_page_url": row.get("landing_page_url", ""),
                "target_location": row.get("target_location", ""),
                "scheduled_at": schedule.get("scheduled_at", ""),
                "schedule_timezone": schedule.get("timezone", ""),
                "currency_code": budget.get("currency_code", "VND"),
                "daily_budget_vnd": budget.get("daily_budget_vnd", 0),
                "manual_cpc_bid_vnd": budget.get("manual_cpc_bid_vnd", 0),
                "keywords": " | ".join(content.get("keywords") or []),
                "headlines": " | ".join(content.get("headlines") or []),
                "descriptions": " | ".join(content.get("descriptions") or []),
                "clicks": metrics.get("clicks", 0),
                "impressions": metrics.get("impressions", 0),
                "cost": metrics.get("cost", 0),
                "conversions": metrics.get("conversions", 0),
                "conversion_value": metrics.get("conversion_value", 0),
            }
        )
    return output.getvalue()
