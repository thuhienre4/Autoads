import os
import threading
import time
from datetime import datetime, timezone

import certifi
import requests
import urllib3
from fastapi import HTTPException
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from app.core.config import settings
from app.services.google_oauth_store import clear_oauth_session, oauth_session


MCC_ACCOUNT_CACHE_TTL_SECONDS = 30
_mcc_account_cache = {
    "accounts": [],
    "synced_at": None,
    "expires_at": 0.0,
    "error": None,
}
_mcc_account_cache_lock = threading.Lock()


def clean_customer_id(value: str | None) -> str | None:
    if not value:
        return None
    return "".join(char for char in value if char.isdigit())


def configured_customer_ids() -> list[str]:
    ids = []
    if settings.GOOGLE_ADS_CUSTOMER_IDS:
        ids.extend(settings.GOOGLE_ADS_CUSTOMER_IDS.split(","))
    if settings.GOOGLE_ADS_CUSTOMER_ID:
        ids.append(settings.GOOGLE_ADS_CUSTOMER_ID)
    cleaned = []
    for value in ids:
        customer_id = clean_customer_id(value)
        if customer_id and customer_id not in cleaned:
            cleaned.append(customer_id)
    login_customer_id = clean_customer_id(settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID)
    return cleaned or ([login_customer_id] if login_customer_id else [])


def _normalize_search_text(value: str | None) -> str:
    return " ".join(str(value or "").lower().split())


def _project_matches_name(project: dict, project_name: str | None) -> bool:
    needle = _normalize_search_text(project_name)
    if not needle:
        return True
    tokens = needle.split()
    haystack = _normalize_search_text(
        " ".join(
            [
                str(project.get("name") or ""),
                str(project.get("url") or ""),
                str(project.get("customer_ids") or ""),
                str(project.get("campaign_id") or ""),
                str(project.get("ad_group_name") or ""),
                str(project.get("ad_group_id") or ""),
            ]
        )
    )
    return needle in haystack or all(token in haystack for token in tokens)


def build_google_ads_client() -> GoogleAdsClient:
    token = oauth_session["token"]
    if not token:
        raise HTTPException(status_code=401, detail="Can login Google truoc khi goi Google Ads API.")
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="OAuth session khong co refresh_token. Hay logout Google, bam Google Login lai va chap nhan consent.",
        )
    config = {
        "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "use_proto_plus": True,
    }
    cert_path = certifi.where()
    os.environ["REQUESTS_CA_BUNDLE"] = cert_path
    os.environ["SSL_CERT_FILE"] = cert_path
    if settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID:
        config["login_customer_id"] = clean_customer_id(settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID)
    try:
        return GoogleAdsClient.load_from_dict(config)
    except RefreshError as exc:
        clear_oauth_session()
        raise HTTPException(
            status_code=401,
            detail="Phiên Google Ads đã hết hạn hoặc bị thu hồi. Hãy bấm Connect Google Ads và cấp lại quyền.",
        ) from exc
    except TransportError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise

        # Local Windows fallback for machines whose Python cert store cannot validate Google TLS.
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=["https://www.googleapis.com/auth/adwords"],
        )
        session = requests.Session()
        session.verify = False
        try:
            credentials.refresh(Request(session=session))
        except RefreshError as refresh_exc:
            clear_oauth_session()
            raise HTTPException(
                status_code=401,
                detail="Phiên Google Ads đã hết hạn hoặc bị thu hồi. Hãy bấm Connect Google Ads và cấp lại quyền.",
            ) from refresh_exc
        return GoogleAdsClient(
            credentials=credentials,
            developer_token=settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            login_customer_id=clean_customer_id(settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID),
            use_proto_plus=True,
        )


def _configured_account_rows() -> list[dict]:
    return [
        {
            "customer_id": customer_id,
            "label": f"Google Ads {customer_id}",
            "descriptive_name": "",
            "manager": False,
            "level": None,
            "currency_code": "",
            "time_zone": "",
            "test_account": False,
            "status": "NOT_SYNCED",
            "status_label": "Not synced",
            "status_description": "Waiting for a live MCC sync.",
            "is_active": None,
            "publish_eligible": True,
            "source": "configuration",
        }
        for customer_id in configured_customer_ids()
    ]


def _customer_status_name(customer_client) -> str:
    status = getattr(customer_client, "status", None)
    value = str(getattr(status, "name", status) or "").upper()
    return {
        "2": "ENABLED",
        "3": "CANCELED",
        "4": "SUSPENDED",
        "5": "CLOSED",
    }.get(value, value or "UNKNOWN")


def _customer_status_details(status: str) -> dict:
    details = {
        "ENABLED": ("Active", "Account is active and can serve ads.", True),
        "CANCELED": ("Canceled", "Account is inactive but an admin can reactivate it.", False),
        "SUSPENDED": ("Suspended", "Account is inactive and requires Google support.", False),
        "CLOSED": ("Closed", "Account is permanently inactive.", False),
        "UNKNOWN": ("Unknown", "Google returned an unknown account status.", False),
        "UNSPECIFIED": ("Unspecified", "Google did not provide an account status.", False),
    }
    label, description, active = details.get(status, details["UNKNOWN"])
    return {
        "status": status,
        "status_label": label,
        "status_description": description,
        "is_active": active,
        "publish_eligible": active,
    }


def discover_mcc_customer_accounts(force: bool = False) -> dict:
    """Return client accounts and their current status beneath the configured MCC.

    Results are cached briefly because the frontend polls account status. When
    Google Ads is unavailable, the last successful discovery (or configured IDs)
    remains available so campaign workflows do not disappear from the UI.
    """
    now = time.monotonic()
    with _mcc_account_cache_lock:
        if (
            not force
            and _mcc_account_cache["accounts"]
            and now < _mcc_account_cache["expires_at"]
        ):
            return {
                "accounts": [dict(item) for item in _mcc_account_cache["accounts"]],
                "synced_at": _mcc_account_cache["synced_at"],
                "source": "mcc_cache",
                "error": _mcc_account_cache["error"],
            }

    fallback_accounts = _configured_account_rows()
    login_customer_id = clean_customer_id(settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID)
    has_ads_oauth = bool(
        oauth_session.get("token")
        and (oauth_session.get("token") or {}).get("refresh_token")
        and "https://www.googleapis.com/auth/adwords" in (oauth_session.get("scopes") or "")
    )
    if not login_customer_id or not settings.GOOGLE_ADS_DEVELOPER_TOKEN or not has_ads_oauth:
        return {
            "accounts": fallback_accounts,
            "synced_at": None,
            "source": "configuration",
            "error": None,
        }

    try:
        client = build_google_ads_client()
        service = client.get_service("GoogleAdsService")
        query = """
            SELECT
              customer_client.client_customer,
              customer_client.descriptive_name,
              customer_client.currency_code,
              customer_client.time_zone,
              customer_client.manager,
              customer_client.level,
              customer_client.status,
              customer_client.test_account,
              customer_client.hidden
            FROM customer_client
            WHERE customer_client.hidden = FALSE
            ORDER BY customer_client.level, customer_client.descriptive_name
        """
        discovered = []
        seen = set()
        for row in service.search(customer_id=login_customer_id, query=query):
            account = row.customer_client
            customer_id = clean_customer_id(getattr(account, "client_customer", None))
            is_manager = bool(getattr(account, "manager", False))
            level = int(getattr(account, "level", 0) or 0)
            if (
                not customer_id
                or customer_id == login_customer_id
                or customer_id in seen
                or is_manager
                or level < 1
            ):
                continue
            seen.add(customer_id)
            descriptive_name = str(getattr(account, "descriptive_name", "") or "").strip()
            status = _customer_status_name(account)
            discovered.append(
                {
                    "customer_id": customer_id,
                    "label": descriptive_name or f"Google Ads {customer_id}",
                    "descriptive_name": descriptive_name,
                    "manager": False,
                    "level": level,
                    "currency_code": str(getattr(account, "currency_code", "") or ""),
                    "time_zone": str(getattr(account, "time_zone", "") or ""),
                    "test_account": bool(getattr(account, "test_account", False)),
                    **_customer_status_details(status),
                    "source": "mcc_live",
                }
            )

        # Preserve explicitly configured accounts if the MCC query omits one due
        # to temporary hierarchy visibility or API access-level restrictions.
        for account in fallback_accounts:
            if account["customer_id"] not in seen:
                discovered.append(account)
                seen.add(account["customer_id"])

        synced_at = datetime.now(timezone.utc).isoformat()
        with _mcc_account_cache_lock:
            _mcc_account_cache.update(
                accounts=[dict(item) for item in discovered],
                synced_at=synced_at,
                expires_at=time.monotonic() + MCC_ACCOUNT_CACHE_TTL_SECONDS,
                error=None,
            )
        return {
            "accounts": discovered,
            "synced_at": synced_at,
            "source": "mcc_live",
            "error": None,
        }
    except Exception as exc:
        error = f"{type(exc).__name__}: {str(exc)}"
        with _mcc_account_cache_lock:
            cached_accounts = [dict(item) for item in _mcc_account_cache["accounts"]]
            cached_synced_at = _mcc_account_cache["synced_at"]
            _mcc_account_cache["expires_at"] = time.monotonic() + MCC_ACCOUNT_CACHE_TTL_SECONDS
            _mcc_account_cache["error"] = error
        return {
            "accounts": cached_accounts or fallback_accounts,
            "synced_at": cached_synced_at,
            "source": "mcc_cache" if cached_accounts else "configuration",
            "error": error,
        }


def available_customer_ids(force: bool = False) -> list[str]:
    """Resolve publishable customer IDs from the live MCC hierarchy.

    Explicitly configured IDs remain only as a fallback when OAuth or the
    Google Ads API is temporarily unavailable.
    """
    account_sync = discover_mcc_customer_accounts(force=force)
    discovered = []
    for account in account_sync["accounts"]:
        if account.get("publish_eligible") is False:
            continue
        customer_id = clean_customer_id(account.get("customer_id"))
        if customer_id and customer_id not in discovered:
            discovered.append(customer_id)
    return discovered or configured_customer_ids()


def fetch_google_ads_landing_page_projects(
    customer_ids: list[str] | None = None,
    limit_per_account: int = 500,
    project_name: str | None = None,
) -> dict:
    client = build_google_ads_client()
    google_ads_service = client.get_service("GoogleAdsService")
    selected_customer_ids = []
    for value in customer_ids or available_customer_ids():
        customer_id = clean_customer_id(value)
        if customer_id and customer_id not in selected_customer_ids:
            selected_customer_ids.append(customer_id)
    if not selected_customer_ids:
        raise HTTPException(status_code=422, detail="Chua co Google Ads customer ID de lay du lieu.")

    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          ad_group.id,
          ad_group.name,
          ad_group_ad.ad.id,
          ad_group_ad.ad.final_urls,
          ad_group_ad.status
        FROM ad_group_ad
        WHERE campaign.status != 'REMOVED'
          AND ad_group_ad.status != 'REMOVED'
        LIMIT {int(limit_per_account)}
    """
    projects = []
    errors = []
    seen = set()

    for customer_id in selected_customer_ids:
        try:
            rows = google_ads_service.search(customer_id=customer_id, query=query)
            for row in rows:
                final_urls = list(row.ad_group_ad.ad.final_urls)
                for url in final_urls:
                    key = (customer_id, str(url))
                    if not url or key in seen:
                        continue
                    seen.add(key)
                    projects.append(
                        {
                            "name": row.campaign.name,
                            "url": str(url),
                            "source": "google_ads_live",
                            "customer_ids": [customer_id],
                            "campaign_id": str(row.campaign.id),
                            "campaign_status": row.campaign.status.name,
                            "ad_group_id": str(row.ad_group.id),
                            "ad_group_name": row.ad_group.name,
                            "ad_id": str(row.ad_group_ad.ad.id),
                        }
                    )
        except GoogleAdsException as exc:
            errors.append(
                {
                    "customer_id": customer_id,
                    "request_id": exc.request_id,
                    "errors": [
                        {
                            "message": error.message,
                            "error_code": error.error_code._pb.__repr__(),
                        }
                        for error in exc.failure.errors
                    ],
                }
            )
        except Exception as exc:
            errors.append(
                {
                    "customer_id": customer_id,
                    "errors": [{"message": f"{type(exc).__name__}: {str(exc)}"}],
                }
            )

    return {
        "source": "google_ads_live",
        "customer_ids": selected_customer_ids,
        "project_name": project_name,
        "projects": [project for project in projects if _project_matches_name(project, project_name)],
        "total_projects_before_filter": len(projects),
        "errors": errors,
    }
