"""Read-only diagnostics: distinguish account state from campaign delivery state."""
from datetime import datetime, timezone

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
        "limitations": "Chẩn đoán đọc trạng thái và lý do phân phối do Google trả về. Chưa kiểm tra thanh toán, xác minh danh tính hoặc lịch sử người/quy tắc đã bấm Pause. Không suy đoán nguyên nhân tạm ngưng tài khoản từ lỗi campaign.",
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
    return result
