import React from "react";

export default function AccountDiagnostics({ accounts = [], apiBase }) {
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
    <div className="mt-3 flex flex-wrap gap-2">
      <select aria-label="Tài khoản cần chẩn đoán" disabled={loading} value={customerId} onChange={e => { setCustomerId(e.target.value); setReport(null); setError(""); }} className="max-w-full rounded-lg border border-slate-300 bg-white p-2 text-sm">
        <option value="">Chọn tài khoản</option>
        {accounts.map(a => <option key={a.customer_id} value={a.customer_id}>{a.label || a.customer_id} · {a.customer_id} · {a.status}</option>)}
      </select>
      <button type="button" disabled={!customerId || loading} onClick={inspect} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">{loading ? "Đang kiểm tra…" : "Kiểm tra nguyên nhân"}</button>
    </div>
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    {report && <div className="mt-4 space-y-3 text-sm">
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
