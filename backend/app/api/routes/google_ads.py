import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel, Field, HttpUrl

from app.core.config import settings
from app.services.google_oauth_store import oauth_session
from app.schemas.ads import AdGenerationRequest
from app.services.ai_service import generate_google_ads_copy
from app.services.google_ads_data_service import build_google_ads_client, discover_mcc_customer_accounts
from app.services.publish_history_service import (
    export_publish_history_csv,
    list_due_scheduled_history,
    list_publish_history,
    record_publish_history,
    update_publish_history_record,
)

router = APIRouter()


class CampaignPublishRequest(BaseModel):
    campaign_name: str = Field(min_length=3)
    daily_budget_vnd: Decimal = Field(gt=0)
    manual_cpc_bid_vnd: Decimal = Field(default=5000, gt=0)
    currency_code: Literal["VND", "USD"] = "VND"
    landing_page_url: HttpUrl
    target_location: str = Field(default="Vietnam")
    excluded_locations: list[str] = []
    excluded_location_ids: list[int] = []
    keywords: list[str] = Field(min_length=1)
    headlines: list[str] = Field(min_length=3, max_length=15)
    descriptions: list[str] = Field(min_length=2, max_length=4)
    customer_ids: list[str] = []
    schedule_enabled: bool = False
    scheduled_at: str | None = None
    schedule_timezone: str = "Asia/Saigon"
    enable_immediately: bool = True
    dry_run: bool = True


def _clean_customer_id(value: str | None) -> str | None:
    if not value:
        return None
    return "".join(char for char in value if char.isdigit())


def _configured_customer_ids() -> list[str]:
    ids = []
    if settings.GOOGLE_ADS_CUSTOMER_IDS:
        ids.extend(settings.GOOGLE_ADS_CUSTOMER_IDS.split(","))
    if settings.GOOGLE_ADS_CUSTOMER_ID:
        ids.append(settings.GOOGLE_ADS_CUSTOMER_ID)
    cleaned = []
    for value in ids:
        customer_id = _clean_customer_id(value)
        if customer_id and customer_id not in cleaned:
            cleaned.append(customer_id)
    login_customer_id = _clean_customer_id(settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID)
    return cleaned or ([login_customer_id] if login_customer_id else [])


def _selected_customer_ids(payload: CampaignPublishRequest) -> list[str]:
    configured = _configured_customer_ids()
    selected = []
    for value in payload.customer_ids:
        customer_id = _clean_customer_id(value)
        if customer_id and customer_id not in selected:
            selected.append(customer_id)
    return selected or configured


def _validate_google_ads_payload(payload: CampaignPublishRequest) -> list[str]:
    errors = []
    minimums = {
        "VND": (Decimal("50000"), Decimal("1000")),
        "USD": (Decimal("2"), Decimal("0.05")),
    }
    minimum_budget, minimum_cpc = minimums[payload.currency_code]
    if payload.daily_budget_vnd < minimum_budget:
        errors.append(
            f"Daily budget nen tu {minimum_budget:g} {payload.currency_code} tro len de co du traffic test."
        )
    if payload.manual_cpc_bid_vnd < minimum_cpc:
        errors.append(
            f"Manual CPC bid nen tu {minimum_cpc:g} {payload.currency_code} tro len de tranh bid qua thap."
        )
    for index, headline in enumerate(payload.headlines, start=1):
        if len(headline) > 30:
            errors.append(f"Headline {index} vuot 30 ky tu.")
    for index, description in enumerate(payload.descriptions, start=1):
        if len(description) > 90:
            errors.append(f"Description {index} vuot 90 ky tu.")
    if len({keyword.lower().strip() for keyword in payload.keywords}) != len(payload.keywords):
        errors.append("Keyword bi trung, nen loai bo ban trung lap truoc khi tao campaign.")
    if payload.schedule_enabled:
        if not payload.scheduled_at:
            errors.append("Can chon thoi gian dang khi bat lich dang.")
        else:
            try:
                datetime.fromisoformat(payload.scheduled_at.replace("Z", "+00:00"))
            except ValueError:
                errors.append("Thoi gian dang khong dung dinh dang ISO datetime.")
    return errors


def _google_ads_error_payload(error) -> dict:
    details = MessageToDict(
        error.details._pb,
        preserving_proto_field_name=True,
        use_integers_for_enums=False,
    )
    policy_entries = details.get("policy_finding_details", {}).get("policy_topic_entries", [])
    return {
        "message": error.message,
        "error_code": error.error_code._pb.__repr__(),
        "field_path": ".".join(
            element.field_name for element in error.location.field_path_elements
        ) if error.location else "",
        "policy_topic_entries": policy_entries,
        "details": details,
    }


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [item.strip() for item in str(value).replace("\n", ",").split(",") if item.strip()]


def _campaign_payload_from_history(record: dict) -> CampaignPublishRequest:
    budget = record.get("budget") or {}
    content = record.get("content") or {}
    plan = record.get("plan") or {}
    campaign_plan = plan.get("campaign") if isinstance(plan.get("campaign"), dict) else {}
    return CampaignPublishRequest(
        campaign_name=record.get("campaign_name") or "Scheduled Search Campaign",
        daily_budget_vnd=budget.get("daily_budget_vnd") or 300000,
        manual_cpc_bid_vnd=budget.get("manual_cpc_bid_vnd") or 5000,
        currency_code=budget.get("currency_code") or record.get("currency_code") or "VND",
        landing_page_url=record.get("landing_page_url"),
        target_location=record.get("target_location") or campaign_plan.get("target_location") or "Vietnam",
        excluded_locations=_as_list(campaign_plan.get("excluded_locations")),
        excluded_location_ids=[
            int(item)
            for item in _as_list(campaign_plan.get("excluded_location_ids"))
            if str(item).strip().isdigit()
        ],
        keywords=_as_list(content.get("keywords")),
        headlines=_as_list(content.get("headlines"))[:15],
        descriptions=_as_list(content.get("descriptions"))[:4],
        customer_ids=_as_list(record.get("customer_ids")),
        enable_immediately=bool(
            record.get("enable_immediately")
            or campaign_plan.get("status") == "ENABLED"
        ),
        dry_run=False,
    )


def _build_google_ads_client() -> GoogleAdsClient:
    return build_google_ads_client()


def _escape_gaql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _resolve_geo_target_ids(client: GoogleAdsClient, customer_id: str, location_names: list[str]) -> dict:
    names = [name.strip() for name in location_names if name.strip()]
    if not names:
        return {"ids": [], "resolved": [], "unresolved": []}

    google_ads_service = client.get_service("GoogleAdsService")
    quoted_names = ", ".join(f"'{_escape_gaql_string(name)}'" for name in names)
    query = f"""
        SELECT
          geo_target_constant.id,
          geo_target_constant.name,
          geo_target_constant.country_code,
          geo_target_constant.target_type,
          geo_target_constant.status
        FROM geo_target_constant
        WHERE geo_target_constant.name IN ({quoted_names})
          AND geo_target_constant.status = 'ENABLED'
    """
    rows = google_ads_service.search(customer_id=customer_id, query=query)
    by_name = {}
    for row in rows:
        geo = row.geo_target_constant
        key = geo.name.lower()
        if key not in by_name:
            by_name[key] = geo

    resolved = []
    unresolved = []
    for name in names:
        geo = by_name.get(name.lower())
        if not geo:
            unresolved.append(name)
            continue
        resolved.append(
            {
                "name": geo.name,
                "id": geo.id,
                "country_code": geo.country_code,
                "target_type": geo.target_type,
            }
        )
    return {"ids": [item["id"] for item in resolved], "resolved": resolved, "unresolved": unresolved}


def _create_campaign_live(payload: CampaignPublishRequest, customer_id: str) -> dict:
    client = _build_google_ads_client()
    suffix = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    budget_service = client.get_service("CampaignBudgetService")
    campaign_service = client.get_service("CampaignService")
    ad_group_service = client.get_service("AdGroupService")
    campaign_criterion_service = client.get_service("CampaignCriterionService")
    criterion_service = client.get_service("AdGroupCriterionService")
    ad_group_ad_service = client.get_service("AdGroupAdService")

    budget_operation = client.get_type("CampaignBudgetOperation")
    budget = budget_operation.create
    budget.name = f"{payload.campaign_name} Budget {suffix}"
    budget.amount_micros = int(payload.daily_budget_vnd * 1_000_000)
    budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    budget_response = budget_service.mutate_campaign_budgets(customer_id=customer_id, operations=[budget_operation])
    budget_resource = budget_response.results[0].resource_name

    campaign_operation = client.get_type("CampaignOperation")
    campaign = campaign_operation.create
    campaign.name = f"{payload.campaign_name} {suffix}"
    campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SEARCH
    # Keep the campaign paused until all dependent resources, especially the
    # ad, have been accepted by Google Ads.
    campaign.status = client.enums.CampaignStatusEnum.PAUSED
    campaign.campaign_budget = budget_resource
    campaign.bidding_strategy_type = client.enums.BiddingStrategyTypeEnum.MANUAL_CPC
    campaign.manual_cpc = client.get_type("ManualCpc")
    campaign.contains_eu_political_advertising = (
        client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
    )
    campaign.network_settings.target_google_search = True
    campaign.network_settings.target_search_network = True
    # Search campaigns must never expand into the Google Display Network.
    campaign.network_settings.target_content_network = False
    campaign_response = campaign_service.mutate_campaigns(customer_id=customer_id, operations=[campaign_operation])
    campaign_resource = campaign_response.results[0].resource_name

    resolved_excluded_locations = _resolve_geo_target_ids(client, customer_id, payload.excluded_locations)
    excluded_location_ids = sorted(set(payload.excluded_location_ids + resolved_excluded_locations["ids"]))
    excluded_location_response = None
    excluded_location_operations = []
    for location_id in excluded_location_ids:
        operation = client.get_type("CampaignCriterionOperation")
        criterion = operation.create
        criterion.campaign = campaign_resource
        criterion.negative = True
        criterion.location.geo_target_constant = client.get_service("GeoTargetConstantService").geo_target_constant_path(
            location_id
        )
        excluded_location_operations.append(operation)
    if excluded_location_operations:
        excluded_location_response = campaign_criterion_service.mutate_campaign_criteria(
            customer_id=customer_id,
            operations=excluded_location_operations,
        )

    ad_group_operation = client.get_type("AdGroupOperation")
    ad_group = ad_group_operation.create
    ad_group.name = f"{payload.campaign_name} - Core {suffix}"
    ad_group.campaign = campaign_resource
    ad_group.status = client.enums.AdGroupStatusEnum.ENABLED
    ad_group.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD
    ad_group.cpc_bid_micros = int(payload.manual_cpc_bid_vnd * 1_000_000)
    ad_group_response = ad_group_service.mutate_ad_groups(customer_id=customer_id, operations=[ad_group_operation])
    ad_group_resource = ad_group_response.results[0].resource_name

    keyword_operations = []
    for keyword_text in payload.keywords:
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = operation.create
        criterion.ad_group = ad_group_resource
        criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
        criterion.keyword.text = keyword_text.strip()
        criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.EXACT
        keyword_operations.append(operation)
    keyword_response = criterion_service.mutate_ad_group_criteria(customer_id=customer_id, operations=keyword_operations)

    ad_operation = client.get_type("AdGroupAdOperation")
    ad_group_ad = ad_operation.create
    ad_group_ad.ad_group = ad_group_resource
    ad_group_ad.status = (
        client.enums.AdGroupAdStatusEnum.ENABLED
        if payload.enable_immediately
        else client.enums.AdGroupAdStatusEnum.PAUSED
    )
    ad_group_ad.ad.final_urls.append(str(payload.landing_page_url))
    responsive_ad = ad_group_ad.ad.responsive_search_ad
    for headline in payload.headlines[:15]:
        asset = client.get_type("AdTextAsset")
        asset.text = headline
        responsive_ad.headlines.append(asset)
    for description in payload.descriptions[:4]:
        asset = client.get_type("AdTextAsset")
        asset.text = description
        responsive_ad.descriptions.append(asset)
    ad_response = ad_group_ad_service.mutate_ad_group_ads(customer_id=customer_id, operations=[ad_operation])

    if payload.enable_immediately:
        enable_operation = client.get_type("CampaignOperation")
        enable_operation.update.resource_name = campaign_resource
        enable_operation.update.status = client.enums.CampaignStatusEnum.ENABLED
        enable_operation.update_mask.paths.append("status")
        campaign_service.mutate_campaigns(
            customer_id=customer_id,
            operations=[enable_operation],
        )

    return {
        "delivery_status": "ENABLED" if payload.enable_immediately else "PAUSED",
        "campaign_resource": campaign_resource,
        "budget_resource": budget_resource,
        "ad_group_resource": ad_group_resource,
        "resolved_excluded_locations": resolved_excluded_locations["resolved"],
        "unresolved_excluded_locations": resolved_excluded_locations["unresolved"],
        "excluded_location_resources": [
            result.resource_name for result in excluded_location_response.results
        ] if excluded_location_response else [],
        "keyword_resources": [result.resource_name for result in keyword_response.results],
        "ad_resource": ad_response.results[0].resource_name,
    }


@router.get("/account/status")
async def account_status(force_refresh: bool = False):
    login_customer_id = _clean_customer_id(settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID)
    account_sync = await asyncio.to_thread(discover_mcc_customer_accounts, force_refresh)
    accounts = account_sync["accounts"]
    customer_ids = [account["customer_id"] for account in accounts]
    customer_id = customer_ids[0] if customer_ids else login_customer_id
    can_publish_live = bool(
        oauth_session["token"]
        and (oauth_session["token"] or {}).get("refresh_token")
        and "https://www.googleapis.com/auth/adwords" in (oauth_session.get("scopes") or "")
        and login_customer_id
        and customer_ids
        and settings.GOOGLE_ADS_DEVELOPER_TOKEN
        and settings.ENABLE_LIVE_GOOGLE_ADS_MUTATIONS
    )
    return {
        "google_oauth_logged_in": bool(oauth_session["token"]),
        "google_user": oauth_session["user"],
        "refresh_token_available": bool((oauth_session["token"] or {}).get("refresh_token")),
        "google_ads_scope_granted": "https://www.googleapis.com/auth/adwords" in (oauth_session.get("scopes") or ""),
        "login_customer_id": login_customer_id,
        "customer_id": customer_id,
        "customer_ids": customer_ids,
        "accounts": [
            {
                **account,
                "selected_by_default": index == 0,
                "can_publish_live": can_publish_live,
            }
            for index, account in enumerate(accounts)
        ],
        "account_sync": {
            "source": account_sync["source"],
            "synced_at": account_sync["synced_at"],
            "error": account_sync["error"],
            "refresh_interval_seconds": 30,
        },
        "developer_token_configured": bool(settings.GOOGLE_ADS_DEVELOPER_TOKEN),
        "live_mutations_enabled": settings.ENABLE_LIVE_GOOGLE_ADS_MUTATIONS,
        "can_validate_campaign": bool(customer_ids),
        "can_publish_live": can_publish_live,
        "access_note": "Test Account Access chi publish duoc vao Google Ads test account cho den khi duoc Basic Access.",
    }


@router.post("/campaigns/publish")
async def publish_campaign(payload: CampaignPublishRequest):
    validation_errors = _validate_google_ads_payload(payload)
    if validation_errors:
        raise HTTPException(status_code=422, detail=validation_errors)

    customer_ids = _selected_customer_ids(payload)
    if not customer_ids:
        raise HTTPException(status_code=422, detail="Chua co Google Ads customer ID de dang campaign.")
    status = await account_status()
    accounts_by_id = {
        account.get("customer_id"): account
        for account in status.get("accounts", [])
    }
    mismatched_accounts = [
        {
            "customer_id": customer_id,
            "currency_code": accounts_by_id[customer_id].get("currency_code"),
        }
        for customer_id in customer_ids
        if customer_id in accounts_by_id
        and accounts_by_id[customer_id].get("currency_code")
        and accounts_by_id[customer_id].get("currency_code") != payload.currency_code
    ]
    if mismatched_accounts:
        account_details = ", ".join(
            f"{item['customer_id']} ({item['currency_code']})"
            for item in mismatched_accounts
        )
        raise HTTPException(
            status_code=422,
            detail=(
                f"Don vi {payload.currency_code} khong khop voi tien te tai khoan Google Ads: "
                f"{account_details}. Hay chon cac tai khoan cung don vi tien te."
            ),
        )

    plan = {
        "customer_ids": customer_ids,
        "campaign": {
            "name": payload.campaign_name,
            "status": "ENABLED" if payload.enable_immediately else "PAUSED",
            "channel_type": "SEARCH",
            "networks": {
                "google_search": True,
                "search_partners": True,
                "display_network": False,
            },
            "target_location": payload.target_location,
            "excluded_locations": payload.excluded_locations,
            "excluded_location_ids": payload.excluded_location_ids,
            "bidding_strategy": "MANUAL_CPC",
        },
        "budget": {
            "daily_budget_vnd": payload.daily_budget_vnd,
            "currency_code": payload.currency_code,
            "delivery_method": "STANDARD",
        },
        "bidding": {
            "strategy": "MANUAL_CPC",
            "manual_cpc_bid_vnd": payload.manual_cpc_bid_vnd,
            "currency_code": payload.currency_code,
        },
        "ad_group": {
            "name": f"{payload.campaign_name} - Core",
            "status": "ENABLED",
            "keywords": [{"text": keyword.strip(), "match_type": "EXACT"} for keyword in payload.keywords],
        },
        "responsive_search_ad": {
            "status": "ENABLED" if payload.enable_immediately else "PAUSED",
            "final_url": str(payload.landing_page_url),
            "headlines": payload.headlines[:15],
            "descriptions": payload.descriptions[:4],
        },
        "schedule": {
            "enabled": payload.schedule_enabled,
            "scheduled_at": payload.scheduled_at,
            "timezone": payload.schedule_timezone,
        },
    }

    if payload.schedule_enabled:
        result = {
            "mode": "scheduled",
            "customer_id": customer_ids[0],
            "customer_ids": customer_ids,
            "ready_for_live": status["can_publish_live"],
            "scheduled_at": payload.scheduled_at,
            "schedule_timezone": payload.schedule_timezone,
            "message": "Campaign da duoc luu lich dang. Chua dang len Google Ads cho den khi co scheduler xu ly.",
            "plan": plan,
        }
        result["history_record"] = record_publish_history(payload, plan, result, result["mode"], "scheduled")
        return result

    if payload.dry_run:
        result = {
            "mode": "dry_run",
            "customer_id": customer_ids[0],
            "customer_ids": customer_ids,
            "ready_for_live": status["can_publish_live"],
            "message": "Campaign da duoc chuan hoa va validate local cho cac tai khoan da chon. Chua dang len Google Ads.",
            "plan": plan,
        }
        result["history_record"] = record_publish_history(payload, plan, result, result["mode"], "validated")
        return result

    if not status["can_publish_live"]:
        raise HTTPException(
            status_code=403,
            detail=(
                "Chua du dieu kien dang live. Can Google OAuth login thanh cong, developer token, "
                "customer id va ENABLE_LIVE_GOOGLE_ADS_MUTATIONS=true."
            ),
        )

    try:
        live_results = []
        live_errors = []
        for customer_id in customer_ids:
            try:
                live_results.append(
                    {
                        "customer_id": customer_id,
                        "result": _create_campaign_live(payload, customer_id),
                    }
                )
            except GoogleAdsException as exc:
                live_errors.append(
                    {
                        "customer_id": customer_id,
                        "request_id": exc.request_id,
                        "errors": [_google_ads_error_payload(error) for error in exc.failure.errors],
                    }
                )
            except Exception as exc:
                live_errors.append(
                    {
                        "customer_id": customer_id,
                        "errors": [
                            {
                                "message": (
                                    "Google Ads API call failed before mutate. "
                                    f"{type(exc).__name__}: {str(exc)}"
                                )
                            }
                        ],
                    }
                )
    except GoogleAdsException as exc:
        errors = [_google_ads_error_payload(error) for error in exc.failure.errors]
        raise HTTPException(status_code=400, detail={"request_id": exc.request_id, "errors": errors}) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Google Ads API call failed before mutate. "
                f"{type(exc).__name__}: {str(exc)}"
            ),
        ) from exc

    if live_errors and not live_results:
        raise HTTPException(status_code=400, detail={"accounts": live_errors})

    result = {
        "mode": "live_created" if not live_errors else "live_partial",
        "customer_id": customer_ids[0],
        "customer_ids": customer_ids,
        "message": (
            "Da tao va bat campaign tren Google Ads. Campaign co the bat dau phan phoi ngay sau khi Google phe duyet quang cao."
            if payload.enable_immediately
            else "Da tao campaign tren Google Ads. Campaign va ad dang PAUSED de an toan."
        ),
        "plan": plan,
        "google_ads": live_results,
        "errors": live_errors,
    }
    result["history_record"] = record_publish_history(
        payload,
        plan,
        result,
        result["mode"],
        "published" if live_results else "failed",
    )
    return result


@router.get("/publish-history")
async def publish_history(customer_id: str | None = None, limit: int = Query(default=100, ge=1, le=500)):
    return {
        "items": list_publish_history(customer_id=customer_id, limit=limit),
    }


@router.get("/publish-history/export.csv")
async def publish_history_export(customer_id: str | None = None):
    csv_content = export_publish_history_csv(customer_id=customer_id)
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=ads_content_history.csv"},
    )


async def run_due_scheduled_campaigns(dry_run: bool = False, limit: int = 10) -> dict:
    due_records = list_due_scheduled_history(limit=limit)
    status = await account_status()
    results = []
    if not status["can_publish_live"] and not dry_run:
        return {
            "processed": 0,
            "dry_run": dry_run,
            "due": len(due_records),
            "blocked": True,
            "message": "Scheduler chua the publish live vi Google Ads OAuth/token/config chua san sang.",
            "results": [],
        }

    for record in due_records:
        payload = _campaign_payload_from_history(record)
        selected_customer_ids = _selected_customer_ids(payload)
        plan = {
            "customer_ids": selected_customer_ids,
            "campaign": {
                "name": payload.campaign_name,
                "status": "ENABLED" if payload.enable_immediately else "PAUSED",
                "channel_type": "SEARCH",
                "networks": {
                    "google_search": True,
                    "search_partners": True,
                    "display_network": False,
                },
                "target_location": payload.target_location,
                "excluded_locations": payload.excluded_locations,
                "excluded_location_ids": payload.excluded_location_ids,
                "bidding_strategy": "MANUAL_CPC",
            },
            "budget": {
                "daily_budget_vnd": payload.daily_budget_vnd,
                "currency_code": payload.currency_code,
                "delivery_method": "STANDARD",
            },
            "bidding": {
                "strategy": "MANUAL_CPC",
                "manual_cpc_bid_vnd": payload.manual_cpc_bid_vnd,
                "currency_code": payload.currency_code,
            },
            "ad_group": {
                "name": f"{payload.campaign_name} - Core",
                "status": "ENABLED",
                "keywords": [{"text": keyword.strip(), "match_type": "EXACT"} for keyword in payload.keywords],
            },
            "responsive_search_ad": {
                "status": "ENABLED" if payload.enable_immediately else "PAUSED",
                "final_url": str(payload.landing_page_url),
                "headlines": payload.headlines[:15],
                "descriptions": payload.descriptions[:4],
            },
            "schedule": record.get("schedule") or {},
        }

        if dry_run:
            results.append(
                {
                    "record_id": record.get("id"),
                    "mode": "scheduler_preview",
                    "customer_ids": selected_customer_ids,
                    "plan": plan,
                }
            )
            continue

        live_results = []
        live_errors = []
        update_publish_history_record(
            record.get("id"),
            {
                "status": "processing",
                "mode": "scheduled_processing",
                "processed_at": datetime.utcnow().isoformat() + "Z",
            },
        )
        for customer_id in selected_customer_ids:
            try:
                live_results.append(
                    {
                        "customer_id": customer_id,
                        "result": _create_campaign_live(payload, customer_id),
                    }
                )
            except GoogleAdsException as exc:
                live_errors.append(
                    {
                        "customer_id": customer_id,
                        "request_id": exc.request_id,
                        "errors": [_google_ads_error_payload(error) for error in exc.failure.errors],
                    }
                )
            except Exception as exc:
                live_errors.append(
                    {
                        "customer_id": customer_id,
                        "errors": [{"message": f"{type(exc).__name__}: {str(exc)}"}],
                    }
                )

        final_mode = "live_created" if not live_errors else ("live_partial" if live_results else "failed")
        final_status = "published" if live_results else "failed"
        updated_record = update_publish_history_record(
            record.get("id"),
            {
                "mode": final_mode,
                "status": final_status,
                "published_at": datetime.utcnow().isoformat() + "Z",
                "result": {
                    "mode": final_mode,
                    "customer_ids": selected_customer_ids,
                    "plan": plan,
                    "google_ads": live_results,
                    "errors": live_errors,
                },
            },
        )
        results.append(
            {
                "record_id": record.get("id"),
                "mode": final_mode,
                "status": final_status,
                "customer_ids": selected_customer_ids,
                "updated_record": updated_record,
            }
        )

    return {
        "processed": 0 if dry_run else len(results),
        "dry_run": dry_run,
        "due": len(due_records),
        "blocked": False,
        "results": results,
    }


@router.post("/scheduled/run-due")
async def run_due_scheduled_endpoint(dry_run: bool = Query(default=True), limit: int = Query(default=10, ge=1, le=50)):
    return await run_due_scheduled_campaigns(dry_run=dry_run, limit=limit)


class AutoPublishRequest(BaseModel):
    ad_request: AdGenerationRequest
    campaign_name: str = Field(min_length=3)
    daily_budget_vnd: Decimal = Field(gt=0)
    manual_cpc_bid_vnd: Decimal = Field(default=5000, gt=0)
    currency_code: Literal["VND", "USD"] = "VND"
    target_location: str = Field(default="Vietnam")
    excluded_locations: list[str] = []
    excluded_location_ids: list[int] = []
    schedule_enabled: bool = False
    scheduled_at: str | None = None
    schedule_timezone: str = "Asia/Saigon"
    dry_run: bool = True


@router.post("/campaigns/auto-publish")
async def auto_publish(payload: AutoPublishRequest):
    """Generate ad copy via AI and publish campaign (or dry run)."""
    # Generate ads content
    ads = generate_google_ads_copy(payload.ad_request)

    # Determine keywords: prefer explicit target_keywords, otherwise use generated keywords
    kws = [k.strip() for k in (payload.ad_request.target_keywords or []) if k.strip()]
    if not kws:
        kws = ads.get("landing_page_alignment", {}).get("keywords_used", []) or []

    campaign_payload = CampaignPublishRequest(
        campaign_name=payload.campaign_name,
        daily_budget_vnd=payload.daily_budget_vnd,
        manual_cpc_bid_vnd=payload.manual_cpc_bid_vnd,
        currency_code=payload.currency_code,
        landing_page_url=payload.ad_request.landing_page_url,
        target_location=payload.target_location,
        excluded_locations=payload.excluded_locations,
        excluded_location_ids=payload.excluded_location_ids,
        keywords=kws,
        headlines=ads.get("headlines", []),
        descriptions=ads.get("descriptions", []),
        schedule_enabled=payload.schedule_enabled,
        scheduled_at=payload.scheduled_at,
        schedule_timezone=payload.schedule_timezone,
        dry_run=payload.dry_run,
    )

    return await publish_campaign(campaign_payload)
