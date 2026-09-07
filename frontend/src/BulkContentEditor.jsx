import React from "react";
import PolicyReview from "./PolicyReview.jsx";
import { lines, editRow, replaceContent } from "./bulk-content.js";

const fields = [["product_name", "Dự án"], ["campaign_name", "Tên campaign"], ["ad_group_name", "Nhóm quảng cáo"], ["landing_page_url", "URL"], ["headlines", "Headline · mỗi dòng một câu · 30 ký tự"], ["descriptions", "Description · mỗi dòng một câu · 90 ký tự"], ["target_keywords", "Keywords · mỗi dòng một từ khóa"], ["primary_cta", "CTA cho đề xuất AI"], ["daily_budget_vnd", "Ngân sách/ngày"], ["manual_cpc_bid_vnd", "CPC"], ["target_location", "Quốc gia mục tiêu"], ["excluded_locations", "Quốc gia loại trừ"], ["excluded_location_ids", "ID địa điểm loại trừ"]];
const button = "rounded-lg border border-blue-200 bg-white px-3 py-2 text-xs font-bold text-blue-800 disabled:opacity-40";

export default function BulkContentEditor({ rows, setRows, selectedIndex, setSelectedIndex, issuesForRow, accounts, busy, generate }) {
  const [find, setFind] = React.useState("");
  const [replacement, setReplacement] = React.useState("");
  const [field, setField] = React.useState("headlines");
  const row = rows[selectedIndex];
  const update = (id, patch) => setRows(current => current.map(r => r.id === id ? editRow(r, patch) : r));
  const selected = rows.filter(r => r.selected && !r.published);
  return <fieldset disabled={busy} className="bulk-content-editor mt-4 min-w-0 space-y-4 disabled:opacity-60">
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" className={button} onClick={() => setRows(current => current.map(r => ({ ...r, selected: !r.published })))}>Chọn tất cả</button>
      <button type="button" className={button} onClick={() => setRows(current => current.map(r => ({ ...r, selected: false })))}>Bỏ chọn</button>
      <button type="button" className={button} disabled={!selected.length} onClick={() => generate(selected)}>Tạo đề xuất AI cho mục đã chọn</button>
      <span className="text-xs text-slate-600">{selected.length} mục đã chọn · sửa nội dung sẽ bỏ trạng thái duyệt</span>
    </div>
    <div className="flex flex-wrap gap-2 rounded-lg bg-slate-50 p-3">
      <select aria-label="Trường tìm thay thế" className="form-input w-auto" value={field} onChange={e => setField(e.target.value)}>{fields.slice(0, 8).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
      <input aria-label="Tìm nội dung" className="form-input w-auto" placeholder="Tìm chính xác" value={find} onChange={e => setFind(e.target.value)} />
      <input aria-label="Nội dung thay thế" className="form-input w-auto" placeholder="Thay bằng" value={replacement} onChange={e => setReplacement(e.target.value)} />
      <button type="button" className={button} disabled={!find || !selected.length} onClick={() => setRows(current => current.map(r => r.selected && !r.published ? replaceContent(r, field, find, replacement) : r))}>Thay trong các mục đã chọn</button>
    </div>
    <div className="max-h-96 overflow-auto rounded-lg border border-slate-200">
      <table className="w-full text-left text-xs"><thead className="bg-slate-100"><tr>{["Chọn", "Nguồn / dự án", "Campaign", "Keywords", "Headline", "Description", "Trạng thái"].map(t => <th key={t} className="p-3">{t}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => { const issues = issuesForRow(r); return <tr key={r.id} className={i === selectedIndex ? "bg-blue-50" : "border-t"}>
          <td className="p-2"><input aria-label={`Chọn ${r.sourceFile} dòng ${r.rowNumber}`} type="checkbox" disabled={r.published} checked={!!r.selected} onChange={e => setRows(current => current.map(x => x.id === r.id ? { ...x, selected: e.target.checked } : x))} /></td>
          <td className="min-w-40 p-2"><button type="button" className="text-left font-bold text-blue-700 underline" onClick={() => setSelectedIndex(i)}>{r.product_name || "Dự án"}</button><p>{r.sourceFile} · dòng {r.rowNumber}</p></td>
          {["campaign_name", "target_keywords", "headlines", "descriptions"].map(key => <td key={key} className="min-w-48 p-2"><textarea aria-label={`${key} dòng ${i + 1}`} disabled={r.published} className="form-input" rows={3} value={r[key] || ""} onFocus={() => setSelectedIndex(i)} onChange={e => update(r.id, { [key]: e.target.value })} />{key === "target_keywords" && <span className="text-slate-500">{lines(r[key]).length} từ khóa · mỗi dòng một từ khóa</span>}</td>)}
          <td className="min-w-48 p-2"><span className="font-bold">{r.published ? "Đã đăng / lên lịch" : r.approved ? "Đã duyệt" : "Chưa duyệt"}</span>{issues.map(issue => <p key={issue} className="text-red-700">{issue}</p>)}{r.result && <p className="mt-2 whitespace-pre-wrap">{r.result}</p>}</td>
        </tr>; })}</tbody>
      </table>
    </div>
    {row && <div className="rounded-xl border border-slate-200 p-4">
      <h3 className="font-black">Chỉnh nội dung · {row.sourceFile} · dòng {row.rowNumber}</h3>
      <fieldset disabled={row.published} className="mt-3 grid min-w-0 gap-3 md:grid-cols-2">
        {fields.map(([key, label]) => <label key={key} className="text-xs font-bold">{label}<textarea className="form-input mt-1" rows={["headlines", "descriptions", "target_keywords"].includes(key) ? 4 : 1} value={row[key] || ""} onChange={e => update(row.id, { [key]: e.target.value })} />{["headlines", "descriptions"].includes(key) && <span className="text-slate-500">{lines(row[key]).map((v, i) => `${i + 1}: ${[...v].length}`).join(" · ")}</span>}</label>)}
        <label className="text-xs font-bold">Tiền tệ<select className="form-input" value={row.currency_code || ""} onChange={e => update(row.id, { currency_code: e.target.value })}><option value="">Chọn</option><option>VND</option><option>USD</option></select></label>
        <label className="text-xs font-bold">Tài khoản đích<select multiple className="form-input" value={row.customer_ids || []} onChange={e => update(row.id, { customer_ids: Array.from(e.target.selectedOptions, o => o.value) })}>{accounts.map(a => <option disabled={a.publish_eligible === false} key={a.customer_id} value={a.customer_id}>{a.name || a.customer_id} · {a.customer_id} · {a.currency_code}</option>)}</select><span>Giữ Ctrl để chọn nhiều tài khoản.</span></label>
        <label className="text-xs font-bold"><input type="checkbox" checked={!!row.schedule_enabled} onChange={e => update(row.id, { schedule_enabled: e.target.checked })} /> Lên lịch đăng</label>
        {row.schedule_enabled && <label className="text-xs font-bold">Thời gian ISO kèm múi giờ<input className="form-input" placeholder="2026-12-01T09:00:00+07:00" value={row.scheduled_at || ""} onChange={e => update(row.id, { scheduled_at: e.target.value })} /></label>}
      </fieldset>
      <div className="my-4 rounded-lg bg-slate-50 p-4"><p className="text-xs text-slate-600">Xem trước · {row.landing_page_url}</p><p className="mt-2 text-lg text-blue-800">{lines(row.headlines).slice(0, 3).join(" | ")}</p><p className="mt-1 text-sm">{lines(row.descriptions).slice(0, 2).join(" ")}</p></div>
      <PolicyReview generated={{ headlines: lines(row.headlines), descriptions: lines(row.descriptions) }} landingPageUrl={row.landing_page_url} />
      {row.suggestion && <div className="my-3 rounded-lg border border-blue-200 p-3"><h4 className="font-bold">Đề xuất AI</h4><p className="whitespace-pre-line text-sm">{row.suggestion.headlines.join("\n")}</p><p className="my-2 whitespace-pre-line text-sm">{row.suggestion.descriptions.join("\n")}</p><button type="button" disabled={row.published} className={button} onClick={() => update(row.id, { headlines: row.suggestion.headlines.join("\n"), descriptions: row.suggestion.descriptions.join("\n"), target_keywords: row.target_keywords || (row.suggestion.landing_page_alignment?.keywords_used || []).join("\n") })}>Chấp nhận đề xuất</button></div>}
      <label className="mt-4 block text-sm font-bold"><input type="checkbox" checked={!!row.approved} disabled={row.published || issuesForRow(row).length > 0} onChange={e => setRows(current => current.map(r => r.id === row.id ? { ...r, approved: e.target.checked } : r))} /> Tôi đã kiểm tra nội dung, tài khoản và ngân sách của mục này</label>
    </div>}
  </fieldset>;
}
