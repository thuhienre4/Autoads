export const DRAFT_KEY = "campaign-draft-v1";

export function readDraft(storage) {
  try {
    const draft = JSON.parse(storage.getItem(DRAFT_KEY));
    return draft && typeof draft === "object" && !Array.isArray(draft) ? draft : {};
  } catch {
    return {};
  }
}

export function saveDraft(storage, draft) {
  try {
    storage.setItem(DRAFT_KEY, JSON.stringify(draft));
    return true;
  } catch {
    return false;
  }
}

export function publishBlocker(status) {
  if (!status.google_oauth_logged_in || !status.google_ads_scope_granted || !status.refresh_token_available) {
    return "Hãy kết nối Google Ads để cấp quyền đăng campaign. Bản nháp sẽ được giữ lại trong tab này.";
  }
  if (!status.developer_token_configured) return "Chưa cấu hình Google Ads developer token trên máy chủ.";
  if (!status.live_mutations_enabled) return "Máy chủ chưa bật ENABLE_LIVE_GOOGLE_ADS_MUTATIONS.";
  if (!status.login_customer_id) return "Chưa cấu hình Google Ads Manager ID trên máy chủ.";
  return status.account_sync?.error || "Chưa có tài khoản Google Ads đủ điều kiện publish. Hãy kiểm tra danh sách tài khoản.";
}
