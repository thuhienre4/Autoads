export const accountGroups = {
  all: "Tất cả",
  suspended: "Bị Google tạm ngưng",
  enabled: "Đang hoạt động",
  inactive: "Đã hủy / đóng",
  unknown: "Chưa xác định",
};

export function accountGroup(account, syncError = false) {
  if (syncError || account.source !== "mcc_live") return "unknown";
  if (account.status === "SUSPENDED") return "suspended";
  if (account.status === "ENABLED") return "enabled";
  if (["CANCELED", "CLOSED"].includes(account.status)) return "inactive";
  return "unknown";
}
