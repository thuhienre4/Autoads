import json
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config" / "affiliate_programs.json"
DATA_DIR = BASE_DIR.parent / "data"
SHORT_LINKS_PATH = DATA_DIR / "affiliate_short_links.json"
CLICK_LOG_PATH = DATA_DIR / "affiliate_click_log.jsonl"
PUBLISH_HISTORY_PATH = DATA_DIR / "publish_history.json"


def _ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SHORT_LINKS_PATH.exists():
        SHORT_LINKS_PATH.write_text("{}", encoding="utf-8")


def _read_json(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_affiliate_config() -> dict:
    return _read_json(CONFIG_PATH, {"default_base_url": "http://localhost:8000/api/v1", "programs": []})


def _normalize_host(host: str | None) -> str:
    host = (host or "").lower().strip()
    return host[4:] if host.startswith("www.") else host


def _domain_matches(host: str, domain: str) -> bool:
    domain = _normalize_host(domain)
    return host == domain or host.endswith(f".{domain}")


def find_program_for_url(url: str, config: dict | None = None) -> dict | None:
    parsed = urlparse(url)
    host = _normalize_host(parsed.hostname)
    if not host:
        return None

    config = config or load_affiliate_config()
    for program in config.get("programs", []):
        if any(_domain_matches(host, domain) for domain in program.get("domains", [])):
            return program
    return None


def _has_affiliate_marker(query_pairs: list[tuple[str, str]], program: dict) -> bool:
    existing_keys = {key.lower() for key, _ in query_pairs}
    markers = set(program.get("duplicate_markers", [])) | set(program.get("affiliate_params", {}).keys())
    return any(marker.lower() in existing_keys for marker in markers)


def _build_url_with_params(url: str, params: dict[str, str]) -> str:
    parsed = urlparse(url)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    existing_keys = {key.lower() for key, _ in query_pairs}
    for key, value in params.items():
        if key.lower() not in existing_keys and value:
            query_pairs.append((key, value))
    return urlunparse(parsed._replace(query=urlencode(query_pairs, doseq=True)))


def _make_short_code(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]


def _store_short_link(code: str, payload: dict) -> None:
    _ensure_data_files()
    links = _read_json(SHORT_LINKS_PATH, {})
    current = links.get(code, {})
    links[code] = {
        **current,
        **payload,
        "code": code,
        "clicks": current.get("clicks", 0),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if "created_at" not in links[code]:
        links[code]["created_at"] = links[code]["updated_at"]
    _write_json(SHORT_LINKS_PATH, links)


def build_affiliate_link(
    original_url: str,
    *,
    base_url: str | None = None,
    use_redirect_tracking: bool = True,
    shorten: bool = True,
    sub_id: str | None = None,
    campaign: str | None = None,
) -> dict:
    _ensure_data_files()
    config = load_affiliate_config()
    use_redirect_tracking = use_redirect_tracking or shorten
    program = find_program_for_url(original_url, config)
    if not program:
        return {
            "matched": False,
            "original_url": original_url,
            "affiliate_url": original_url,
            "tracking_url": None,
            "short_url": None,
            "already_wrapped": False,
            "message": "No configured affiliate program matched this domain.",
        }

    parsed = urlparse(original_url)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    already_wrapped = _has_affiliate_marker(query_pairs, program)
    affiliate_params = dict(program.get("affiliate_params", {}))
    if sub_id:
        affiliate_params.setdefault("sub_id", sub_id)
    if campaign:
        affiliate_params.setdefault("utm_campaign", campaign)

    affiliate_url = original_url if already_wrapped else _build_url_with_params(original_url, affiliate_params)
    code = _make_short_code(affiliate_url)
    root_url = (base_url or config.get("default_base_url") or "http://localhost:8000").rstrip("/")
    public_root_url = root_url[:-7] if root_url.endswith("/api/v1") else root_url
    tracking_url = f"{public_root_url}/go/{code}" if use_redirect_tracking else None
    short_url = tracking_url if shorten else None

    _store_short_link(
        code,
        {
            "original_url": original_url,
            "affiliate_url": affiliate_url,
            "program_name": program.get("name"),
            "network": program.get("network"),
            "already_wrapped": already_wrapped,
        },
    )

    return {
        "matched": True,
        "original_url": original_url,
        "affiliate_url": affiliate_url,
        "tracking_url": tracking_url,
        "short_url": short_url,
        "short_code": code,
        "already_wrapped": already_wrapped,
        "program": {
            "name": program.get("name"),
            "network": program.get("network"),
            "domains": program.get("domains", []),
            "signup_url": program.get("signup_url"),
        },
        "message": "Affiliate link generated." if not already_wrapped else "URL already contains affiliate parameters; duplicate wrapping skipped.",
    }


def scan_affiliate_projects(projects: list[dict] | None = None, include_unmatched: bool = False) -> dict:
    config = load_affiliate_config()
    source = projects or []
    if not projects:
        rows = _read_json(PUBLISH_HISTORY_PATH, [])
        if isinstance(rows, dict):
            rows = [rows]
        seen = set()
        for row in rows:
            url = row.get("landing_page_url") or row.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            source.append(
                {
                    "name": row.get("campaign_name") or row.get("product_name") or urlparse(url).netloc,
                    "url": url,
                    "source": "publish_history",
                    "last_used_at": row.get("created_at"),
                    "customer_ids": row.get("customer_ids") or [],
                }
            )

    matched = []
    unmatched = []
    for project in source:
        url = str(project.get("url") or project.get("landing_page_url") or "").strip()
        if not url:
            continue
        program = find_program_for_url(url, config)
        row = {
            "name": project.get("name") or project.get("campaign_name") or urlparse(url).netloc,
            "url": url,
            "source": project.get("source") or "manual",
            "last_used_at": project.get("last_used_at") or project.get("created_at"),
            "customer_ids": project.get("customer_ids") or [],
            "matched": bool(program),
            "program": None,
        }
        if program:
            row["program"] = {
                "name": program.get("name"),
                "network": program.get("network"),
                "domains": program.get("domains", []),
                "signup_url": program.get("signup_url"),
            }
            matched.append(row)
        else:
            unmatched.append(row)

    return {
        "source": "provided" if projects else "publish_history",
        "matched_count": len(matched),
        "unmatched_count": len(unmatched),
        "items": matched + (unmatched if include_unmatched else []),
    }


def _normalize_search_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _project_from_program(program: dict) -> dict:
    domain = (program.get("domains") or [""])[0]
    return {
        "name": program.get("name") or domain,
        "url": f"https://{domain}" if domain else "",
        "source": "affiliate_config",
    }


def search_affiliate_projects_by_name(query: str, include_unmatched: bool = False, limit: int = 25) -> dict:
    needle = _normalize_search_text(query)
    if not needle:
        return {
            "query": query,
            "source": "publish_history_and_affiliate_config",
            "matched_count": 0,
            "unmatched_count": 0,
            "items": [],
            "suggestions": [],
        }

    config = load_affiliate_config()
    candidates = []
    seen_urls = set()

    rows = _read_json(PUBLISH_HISTORY_PATH, [])
    if isinstance(rows, dict):
        rows = [rows]
    for row in rows:
        url = row.get("landing_page_url") or row.get("url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        candidates.append(
            {
                "name": row.get("campaign_name") or row.get("product_name") or urlparse(url).netloc,
                "url": url,
                "source": "publish_history",
                "last_used_at": row.get("created_at"),
                "customer_ids": row.get("customer_ids") or [],
            }
        )

    for program in config.get("programs", []):
        project = _project_from_program(program)
        if project["url"] and project["url"] not in seen_urls:
            seen_urls.add(project["url"])
            candidates.append(project)

    matched = []
    suggestions = []
    for project in candidates:
        url = str(project.get("url") or "")
        domain = _normalize_host(urlparse(url).hostname)
        haystack = _normalize_search_text(
            " ".join(
                [
                    str(project.get("name") or ""),
                    domain,
                    url,
                    str(project.get("source") or ""),
                ]
            )
        )
        name_hit = needle in haystack or all(token in haystack for token in needle.split())
        if not name_hit:
            if any(token and token in haystack for token in needle.split()):
                suggestions.append(project.get("name") or domain or url)
            continue

        program = find_program_for_url(url, config)
        row = {
            "name": project.get("name") or domain,
            "url": url,
            "domain": domain,
            "source": project.get("source") or "manual",
            "last_used_at": project.get("last_used_at"),
            "customer_ids": project.get("customer_ids") or [],
            "matched": bool(program),
            "has_affiliate": bool(program),
            "affiliate_url": url if program else None,
            "signup_url": program.get("signup_url") if program else None,
            "program": None,
        }
        if program:
            row["program"] = {
                "name": program.get("name"),
                "network": program.get("network"),
                "domains": program.get("domains", []),
                "signup_url": program.get("signup_url"),
                "affiliate_params": program.get("affiliate_params", {}),
            }

        # A name filter is an explicit lookup, so matching projects should not
        # disappear just because their domain is not configured as an affiliate.
        matched.append(row)

    return {
        "query": query,
        "source": "publish_history_and_affiliate_config",
        "matched_count": len([item for item in matched if item["matched"]]),
        "unmatched_count": len([item for item in matched if not item["matched"]]),
        "items": matched[:limit],
        "suggestions": sorted(set(suggestions))[:8],
    }


def get_short_link(code: str) -> dict | None:
    _ensure_data_files()
    return _read_json(SHORT_LINKS_PATH, {}).get(code)


def record_click(code: str, *, user_agent: str | None = None, referer: str | None = None, ip: str | None = None) -> dict | None:
    _ensure_data_files()
    links = _read_json(SHORT_LINKS_PATH, {})
    link = links.get(code)
    if not link:
        return None

    link["clicks"] = link.get("clicks", 0) + 1
    link["last_clicked_at"] = datetime.now(timezone.utc).isoformat()
    links[code] = link
    _write_json(SHORT_LINKS_PATH, links)

    event = {
        "code": code,
        "clicked_at": link["last_clicked_at"],
        "affiliate_url": link["affiliate_url"],
        "network": link.get("network"),
        "program_name": link.get("program_name"),
        "user_agent": user_agent,
        "referer": referer,
        "ip": ip,
    }
    with CLICK_LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(event, ensure_ascii=False) + "\n")
    return link


def get_link_stats(code: str) -> dict | None:
    link = get_short_link(code)
    if not link:
        return None
    return {
        "code": code,
        "clicks": link.get("clicks", 0),
        "affiliate_url": link.get("affiliate_url"),
        "original_url": link.get("original_url"),
        "network": link.get("network"),
        "program_name": link.get("program_name"),
        "created_at": link.get("created_at"),
        "last_clicked_at": link.get("last_clicked_at"),
    }
