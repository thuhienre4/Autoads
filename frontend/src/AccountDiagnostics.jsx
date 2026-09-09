import React from "react";
import SuspensionNotice from "./SuspensionNotice.jsx";
import { accountGroup, accountGroups } from "./account-health.js";

export default function AccountDiagnostics({ accounts = [], apiBase, syncError = false }) {
  const [filter, setFilter] = React.useState("all");
  const filtered = accounts.filter(a => filter === "all" || accountGroup(a, syncError) === filter);
  const [customerId, setCustomerId] = React.useState("");
  const [report, setReport] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const inspect = async () => {
    setLoading(true); setError(""); setReport(null);
    try {
      const response = await fetch(`${apiBase}/google-ads/accounts/${customerId}/diagnostics`);
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Không đọc được chẩn đoán tài khoản.");
      setReport(data);
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };
  return <section className="surface-card p-4" aria-label="Chẩn đoán tài khoản Ads">
    <h2 className="text-base font-black">Kiểm tra tạm ngưng / tạm dừng</h2>
    <p className="mt-1 text-sm text-slate-600">Phân biệt trạng thái tài khoản với lý do campaign không phân phối.</p>
    <p className="mt-1 text-xs text-slate-500">Đang hoạt động không có nghĩa là đã kiểm tra hết lỗi. Chọn tài khoản và kiểm tra nguyên nhân để xem kết luận.</p>
    <div className="mt-3 flex flex-wrap gap-2">{Object.entries(accountGroups).map(([key, label]) => <button key={key} type="button" disabled={loading} aria-pressed={filter === key} onClick={() => { setFilter(key); setCustomerId(""); setReport(null); setError(""); }} className={`rounded-lg border px-3 py-2 text-xs font-bold ${filter === key ? "border-blue-500 bg-blue-50 text-blue-800" : "border-slate-200"}`}>{label} ({key === "all" ? accounts.length : accounts.filter(a => accountGroup(a, syncError) === key).length})</button>)}</div>
    <div className="mt-3 flex flex-wrap gap-2">
      <select aria-label="Tài khoản cần chẩn đoán" disabled={loading} value={customerId} onChange={e => { setCustomerId(e.target.value); setReport(null); setError(""); }} className="max-w-full rounded-lg border border-slate-300 bg-white p-2 text-sm">
        <option value="">Chọn tài khoản</option>
        {filtered.map(a => <option key={a.customer_id} value={a.customer_id}>{a.label || a.customer_id} · {a.customer_id} · {a.status}</option>)}
      </select>
      <button type="button" disabled={!customerId || loading} onClick={inspect} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">{loading ? "Đang kiểm tra…" : "Kiểm tra nguyên nhân"}</button>
    </div>
    {customerId && <SuspensionNotice key={customerId} customerId={customerId} />}
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    {report && <div className="mt-4 space-y-3 text-sm">
      {report.classification && <p role="status" className={`rounded-lg border p-3 font-bold ${report.classification.code === "suspended" ? "border-red-200 bg-red-50 text-red-800" : report.classification.code === "no_issues_detected" ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-amber-200 bg-amber-50 text-amber-900"}`}>{report.classification.label}</p>}
      {report.status === "SUSPENDED" && report.suspension_reason && <div className="rounded-lg border border-red-200 bg-red-50 p-3"><h3 className="font-bold">Tạm ngưng vì chính sách nào?</h3><p className="mt-1">{report.suspension_reason.message}</p></div>}
      {report.verification && <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
        <h3 className="font-bold">Xác minh nhà quảng cáo</h3>
        {report.verification.error && <p className="mt-1 text-amber-800">{report.verification.error}</p>}
        {report.verification.checked && !report.verification.programs.length && <p className="mt-1">API không trả về chương trình xác minh danh tính. Điều này không xác nhận tài khoản đã hoàn tất mọi yêu cầu xác minh.</p>}
        {report.verification.programs.map((p, i) => <div key={i} className="mt-2"><p className="font-semibold">{p.label}</p><p className="text-xs">Google: {p.program} · {p.status}</p>{p.start_deadline && <p>Hạn bắt đầu (nguyên văn Google): {p.start_deadline}</p>}{p.completion_deadline && <p>Hạn hoàn tất (nguyên văn Google): {p.completion_deadline}</p>}</div>)}
        <p className="mt-2">Chưa xác nhận tài khoản bị tạm dừng để xác minh. Hãy đối chiếu thông báo tạm dừng và các nhiệm vụ xác minh trong Google Ads.</p>
        <p className="mt-1 text-xs text-slate-500">Đọc lúc: {new Date(report.verification.checked_at).toLocaleString("vi-VN")} · Kết quả được lưu tối đa 5 phút.</p>
      </div>}
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3"><h3 className="font-bold">{report.account_name} · {report.title}</h3><p className="mt-1">{report.action}</p><p className="mt-2 text-xs text-slate-500">Mã trạng thái: {report.status} · Kiểm tra: {new Date(report.checked_at).toLocaleString("vi-VN")}</p></div>
      {report.sync_error && <p className="text-amber-800">Đồng bộ tài khoản gặp lỗi; trạng thái có thể là dữ liệu cũ: {report.sync_error}</p>}
      {!!report.api_errors?.length && <div className="rounded-lg border border-amber-200 bg-amber-50 p-3"><strong>Chưa đọc được campaign</strong>{report.api_errors.map((item, i) => <p key={i} className="mt-1 break-words">{item.message} · {item.code}{item.request_id ? ` · Request ID: ${item.request_id}` : ""}</p>)}</div>}
      {report.campaigns_checked && !report.campaigns.length && <p>Không tìm thấy campaign chưa bị xóa trong tài khoản này.</p>}
      {report.truncated && <p>Đang hiển thị 100 campaign đầu tiên; xem Google Ads để kiểm tra đầy đủ.</p>}
      <div className="max-h-96 space-y-2 overflow-auto">{report.campaigns.map(c => <div key={c.id} className="rounded-lg border border-slate-200 p-3"><h4 className="font-bold">{c.name} · {c.id}</h4><p className="mt-1">Trạng thái cài đặt: {c.status} · Phân phối: {c.primary_status}</p>{c.reasons.length ? c.reasons.map(r => <div key={r.code} className="mt-2"><p className="font-semibold">{r.label}</p><p>{r.action}</p><p className="text-xs text-slate-500">Google: {r.code}</p></div>) : <p className="mt-2 text-slate-500">Google chưa trả về lý do phân phối cụ thể.</p>}</div>)}</div>
      <p className="text-xs leading-5 text-slate-500">{report.limitations}</p>
      <a href="https://ads.google.com/aw/overview" target="_blank" rel="noreferrer" className="inline-block font-bold text-blue-700 underline">Mở Google Ads · chọn đúng tài khoản {report.customer_id}</a>
    </div>}
  </section>;
}
