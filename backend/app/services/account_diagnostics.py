"""Read-only diagnostics: distinguish account state from campaign delivery state."""
from datetime import datetime, timezone
from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from time import monotonic

from fastapi import HTTPException
from google.ads.googleads.errors import GoogleAdsException

from app.services.google_ads_data_service import build_google_ads_client, discover_mcc_customer_accounts

ACCOUNT_GUIDANCE = {
    "ENABLED": ("Tài khoản đang hoạt động", "Kiểm tra trạng thái phân phối từng campaign bên dưới. Active không bảo đảm quảng cáo đang phân phối."),
    "SUSPENDED": ("Tài khoản bị Google tạm ngưng", "Mở thông báo trong Google Ads và email quản trị để xem lý do cụ thể và hướng dẫn kháng nghị. Trạng thái SUSPENDED không cho biết vi phạm nào hoặc thời hạn khôi phục."),
    "CANCELED": ("Tài khoản đã hủy hoạt động", "Quản trị viên kiểm tra phần trạng thái tài khoản trong Google Ads để kích hoạt lại. Đây là trạng thái tài khoản, không phải nút Pause campaign."),
    "CLOSED": ("Tài khoản đã đóng", "Kiểm tra thông báo tài khoản và liên hệ hỗ trợ Google Ads nếu cần xác minh khả năng khôi phục."),
}
REASONS = {
    "CAMPAIGN_PAUSED": ("Campaign đang tạm dừng", "Kiểm tra ai hoặc quy tắc nào đã đổi trạng thái trong Lịch sử thay đổi trước khi bật lại."),
    "CAMPAIGN_REMOVED": ("Campaign đã bị xóa", "Kiểm tra Lịch sử thay đổi trong Google Ads."),
    "CAMPAIGN_ENDED": ("Campaign đã qua ngày kết thúc", "Kiểm tra ngày kết thúc campaign."),
    "CAMPAIGN_PENDING": ("Campaign chưa tới ngày bắt đầu", "Kiểm tra ngày bắt đầu và múi giờ tài khoản."),
    "BUDGET_CONSTRAINED": ("Phân phối bị giới hạn ngân sách", "Kiểm tra ngân sách và chi tiêu thực tế trước khi điều chỉnh."),
    "HAS_ADS_DISAPPROVED": ("Có quảng cáo bị từ chối", "Xem lý do chính sách của từng quảng cáo trong Google Ads."),
    "HAS_ADS_LIMITED_BY_POLICY": ("Có quảng cáo bị giới hạn chính sách", "Kiểm tra Policy Manager và thị trường được phép phân phối."),
    "MOST_ADS_UNDER_REVIEW": ("Phần lớn quảng cáo đang được xét duyệt", "Theo dõi trạng thái xét duyệt trong Google Ads."),
    "NO_ADS": ("Không có quảng cáo", "Kiểm tra quảng cáo trong các nhóm quảng cáo."),
    "NO_ELIGIBLE_ADS": ("Không có quảng cáo đủ điều kiện", "Kiểm tra trạng thái quảng cáo và chính sách."),
    "NO_AD_GROUPS": ("Không có nhóm quảng cáo", "Kiểm tra cấu trúc campaign."),
    "NO_ELIGIBLE_AD_GROUPS": ("Không có nhóm quảng cáo đủ điều kiện", "Kiểm tra nhóm quảng cáo đang bật hay tạm dừng."),
}


def enum_name(value):
    return str(getattr(value, "name", value) or "UNKNOWN")


_verification_cache = OrderedDict()
_verification_lock = Lock()


def read_verification(customer_id):
    # This endpoint has tighter Google rate limits; reuse read results for 5 minutes.
    with _verification_lock:
        cached = _verification_cache.get(customer_id)
        if cached and cached[0] > monotonic():
            return deepcopy(cached[1])
    result = {"checked": False, "programs": [], "checked_at": datetime.now(timezone.utc).isoformat(),
              "error": "", "source": "Google IdentityVerificationService",
              "pause_confirmed": False}
    try:
        service = build_google_ads_client().get_service("IdentityVerificationService")
        response = service.get_identity_verification(customer_id=customer_id, timeout=20)
        labels = {"PENDING_USER_ACTION": "Cần hoàn tất xác minh nhà quảng cáo",
                  "PENDING_REVIEW": "Google đang xét duyệt xác minh",
                  "SUCCESS": "Đã hoàn tất xác minh danh tính",
                  "FAILURE": "Xác minh chưa thành công"}
        for item in response.identity_verification:
            progress = item.verification_progress
            requirement = item.identity_verification_requirement
            status = enum_name(progress.program_status)
            result["programs"].append({
                "program": enum_name(item.verification_program), "status": status,
                "label": labels.get(status, "Trạng thái xác minh: " + status),
                "start_deadline": requirement.verification_start_deadline_time,
                "completion_deadline": requirement.verification_completion_deadline_time,
            })
        result["checked"] = True
    except GoogleAdsException as exc:
        result["error"] = "; ".join(error.message for error in exc.failure.errors)
        result["request_id"] = exc.request_id
    except Exception:
        result["error"] = "Chưa đọc được xác minh nhà quảng cáo. Kiểm tra trực tiếp trong Google Ads."
    with _verification_lock:
        _verification_cache[customer_id] = (monotonic() + (300 if result["checked"] else 30), deepcopy(result))
        _verification_cache.move_to_end(customer_id)
        while len(_verification_cache) > 128:
            _verification_cache.popitem(last=False)
    return result


def campaign_diagnostic(campaign):
    status = enum_name(campaign.status)
    codes = [enum_name(reason) for reason in campaign.primary_status_reasons]
    # Configured pause is evidence even if serving reasons have not refreshed yet.
    if status == "PAUSED" and "CAMPAIGN_PAUSED" not in codes:
        codes.insert(0, "CAMPAIGN_PAUSED")
    return {
        "id": str(campaign.id), "name": campaign.name, "status": status,
        "primary_status": enum_name(campaign.primary_status),
        "reasons": [{"code": code, "label": REASONS.get(code, (code, ""))[0],
                     "action": REASONS.get(code, ("", "Xem chi tiết trạng thái phân phối trong Google Ads."))[1]}
                    for code in codes],
    }


def classify_report(report):
    fresh = report.get("account_source") == "mcc_live" and not report.get("sync_error")
    status = report["status"]
    if not fresh:
        return {"code": "unknown", "label": "Chưa đủ dữ liệu mới để kết luận"}
    if status == "SUSPENDED":
        return {"code": "suspended", "label": "Tài khoản bị Google tạm ngưng"}
    if status in {"CANCELED", "CLOSED"}:
        return {"code": "inactive", "label": "Tài khoản đã hủy / đóng"}
    verification = report.get("verification")
    if verification is not None:
        if not verification["checked"]:
            return {"code": "unknown", "label": "Chưa kiểm tra được xác minh nhà quảng cáo"}
        if any(p["status"] != "SUCCESS" for p in verification["programs"]):
            return {"code": "verification_attention", "label": "Xác minh nhà quảng cáo cần kiểm tra; chưa xác nhận tài khoản bị tạm dừng"}
    if status != "ENABLED" or not report["campaigns_checked"] or report["api_errors"] or report["truncated"]:
        return {"code": "unknown", "label": "Chưa đủ dữ liệu để kết luận không lỗi"}
    campaigns = report["campaigns"]
    issues = [c for c in campaigns if c["status"] != "PAUSED" and (
        c["primary_status"] != "ELIGIBLE" or c["reasons"])]
    if issues:
        return {"code": "attention", "label": "Tài khoản hoạt động, campaign cần kiểm tra"}
    if any(c["status"] == "PAUSED" for c in campaigns):
        return {"code": "paused_campaigns", "label": "Tài khoản hoạt động, có campaign tạm dừng"}
    if not campaigns:
        return {"code": "no_campaigns", "label": "Tài khoản hoạt động, chưa có campaign để kiểm tra"}
    return {"code": "no_issues_detected", "label": "Chưa phát hiện lỗi trong phạm vi đã kiểm tra"}


def diagnose_account(customer_id):
    sync = discover_mcc_customer_accounts(force=True)
    account = next((a for a in sync["accounts"] if a["customer_id"] == customer_id), None)
    if account is None:
        raise HTTPException(status_code=404, detail="Tài khoản không có trong MCC đã kết nối.")
    status = account.get("status", "NOT_SYNCED")
    title, action = ACCOUNT_GUIDANCE.get(status, ("Chưa xác định được trạng thái tài khoản", "Đồng bộ MCC và kiểm tra quyền truy cập tài khoản."))
    result = {
        "customer_id": customer_id, "account_name": account.get("label", customer_id),
        "status": status, "title": title, "action": action,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "account_synced_at": sync.get("synced_at"),
        "account_source": sync.get("source"), "sync_error": sync.get("error"),
        "campaigns": [], "campaigns_checked": False, "truncated": False,
        "api_errors": [],
        "limitations": "Đã bổ sung kiểm tra xác minh danh tính khi API cho phép. Chưa kiểm tra thanh toán, mọi chương trình xác minh khác hoặc lịch sử người/quy tắc đã bấm Pause. Trạng thái xác minh không xác nhận nguyên nhân tài khoản bị tạm dừng. Lỗi campaign không phải bằng chứng về chính sách khiến tài khoản bị ngưng.",
    }
    try:
        service = build_google_ads_client().get_service("GoogleAdsService")
        rows = service.search(customer_id=customer_id, query="""
            SELECT campaign.id, campaign.name, campaign.status,
                   campaign.primary_status, campaign.primary_status_reasons
            FROM campaign WHERE campaign.status != 'REMOVED'
            ORDER BY campaign.id LIMIT 101
        """)
        campaigns = [campaign_diagnostic(row.campaign) for row in rows]
        result.update(campaigns=campaigns[:100], campaigns_checked=True, truncated=len(campaigns) > 100)
    except GoogleAdsException as exc:
        result["api_errors"] = [{"message": error.message, "code": str(error.error_code), "request_id": exc.request_id} for error in exc.failure.errors]
    except HTTPException as exc:
        result["api_errors"] = [{"message": str(exc.detail), "code": str(exc.status_code)}]
    except Exception:
        result["api_errors"] = [{"message": "Không đọc được trạng thái campaign. Thử lại hoặc kiểm tra kết nối Google Ads.", "code": "DIAGNOSTIC_FETCH_FAILED"}]
    result["verification"] = read_verification(customer_id)
    result["suspension_reason"] = {
        "confirmed": False,
        "message": "Chưa có tên chính sách gây tạm ngưng từ dữ liệu API đã đọc. Đối chiếu nguyên văn thông báo tạm ngưng trong Google Ads hoặc email Google gửi cho đúng tài khoản.",
    }
    result["classification"] = classify_report(result)
    return result
