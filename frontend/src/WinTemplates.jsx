import React from "react";
import WinTemplateUpload from "./WinTemplateUpload.jsx";
import { assetLines, exampleTemplate } from "./win-templates.js";

const input = "mt-1 w-full min-w-0 rounded-lg border border-slate-200 bg-white p-2.5 text-sm text-slate-800";
const button = "rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold disabled:opacity-50";
const empty = { name: "", notes: "", headlines: "", descriptions: "" };

export default function WinTemplates({ apiBase, value, onChange, disabled = false }) {
  const [templates, setTemplates] = React.useState([]);
  const [draft, setDraft] = React.useState(empty);
  const [error, setError] = React.useState("");
  const [notice, setNotice] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [pendingDelete, setPendingDelete] = React.useState(false);
  const selected = templates.find((item) => item.id === value);
  async function request(path = "", options = {}) {
    const response = await fetch(`${apiBase}/ai/win-templates${path}`, options);
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : (data.detail || []).map((item) => item.msg).join(" · ") || "Không lưu được mẫu.");
    return data;
  }
  async function refresh() {
    setBusy(true); setError("");
    try { setTemplates((await request()).templates); }
    catch { setError("Không tải được thư viện mẫu. Hãy thử tải lại."); }
    finally { setBusy(false); }
  }
  React.useEffect(() => { refresh(); }, [apiBase]);
  async function save() {
    setBusy(true); setError(""); setNotice("");
    try {
      const saved = await request("", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...draft, headlines: assetLines(draft.headlines), descriptions: assetLines(draft.descriptions) }) });
      setTemplates((current) => [saved, ...current]); onChange(saved.id); setDraft(empty);
      setNotice("Đã lưu và chọn mẫu. Bấm tạo RSA để AI áp dụng cách viết.");
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  async function remove() {
    setBusy(true); setError(""); setNotice("");
    try {
      await request(`/${encodeURIComponent(value)}`, { method: "DELETE" });
      setTemplates((current) => current.filter((item) => item.id !== value)); onChange(""); setPendingDelete(false);
      setNotice("Đã xóa mẫu.");
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  return <fieldset disabled={disabled || busy} className="min-w-0 space-y-3 rounded-xl border border-blue-100 bg-blue-50/50 p-3 disabled:opacity-60">
    <legend className="px-1 text-sm font-black text-blue-900">Content win · Google Ads</legend>
    <p className="text-xs leading-5 text-slate-600">Lưu quảng cáo hiệu quả làm mẫu. AI tham khảo cấu trúc và giọng văn khi viết cho sản phẩm mới.</p>
    <WinTemplateUpload request={request} disabled={disabled || busy} onSaved={(saved) => { setTemplates(items => [...saved, ...items]); onChange(saved[0].id); setNotice(""); }} />
    <label className="block text-xs font-bold">Mẫu dùng khi tạo RSA
      <select className={input} value={value || ""} onChange={(event) => { onChange(event.target.value); setPendingDelete(false); setNotice(""); }}>
        <option value="">Không dùng mẫu</option>
        {value && !selected && <option value={value}>Mẫu chưa tải được hoặc đã xóa — chọn lại</option>}
        {templates.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
    </label>
    <button type="button" className={button} onClick={refresh}>Tải lại thư viện</button>
    {selected && <details className="text-xs text-slate-700">
      <summary className="cursor-pointer font-bold">Xem mẫu · {selected.headlines.length} headlines / {selected.descriptions.length} descriptions</summary>
      <p className="mt-2 whitespace-pre-wrap break-words">{selected.notes}</p>
      <p className="mt-2 font-bold">Headlines</p><ul className="list-inside list-disc break-words">{selected.headlines.map((line, i) => <li key={i}>{line}</li>)}</ul>
      <p className="mt-2 font-bold">Descriptions</p><ul className="list-inside list-disc break-words">{selected.descriptions.map((line, i) => <li key={i}>{line}</li>)}</ul>
      <button type="button" className={`${button} mt-3 text-red-700`} onClick={() => setPendingDelete(true)}>Xóa mẫu</button>
      {pendingDelete && <div className="mt-2 flex flex-wrap gap-2"><span className="w-full">Xóa “{selected.name}” khỏi thư viện?</span><button type="button" className={button} onClick={remove}>Xác nhận xóa</button><button type="button" className={button} onClick={() => setPendingDelete(false)}>Hủy</button></div>}
    </details>}
    <details>
      <summary className="cursor-pointer text-sm font-bold text-blue-800">Hoặc dán content win trực tiếp</summary>
      <div className="mt-3 space-y-3">
        <p className="text-xs leading-5 text-slate-600">Dán headline và description vào các ô bên dưới. Nếu dùng TXT, file cần hai mục [Headlines] và [Descriptions], mỗi nội dung một dòng.</p>
        <a className="block text-xs font-bold text-blue-700 underline" download="content-win.json" href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(exampleTemplate, null, 2))}`}>Tải file mẫu JSON</a>
        <label className="block text-xs font-bold">Tên mẫu<input className={input} maxLength={120} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label>
        <label className="block text-xs font-bold">Headlines mẫu · 1–15 dòng, tối đa 30 ký tự/dòng<textarea rows={4} className={input} value={draft.headlines} onChange={(e) => setDraft({ ...draft, headlines: e.target.value })} /></label>
        <label className="block text-xs font-bold">Descriptions mẫu · 1–4 dòng, tối đa 90 ký tự/dòng<textarea rows={4} className={input} value={draft.descriptions} onChange={(e) => setDraft({ ...draft, descriptions: e.target.value })} /></label>
        <label className="block text-xs font-bold">Ghi chú cách viết / kết quả đã đạt<textarea rows={2} maxLength={2000} className={input} value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} /></label>
        <button type="button" className={`${button} bg-blue-600 text-white`} disabled={!draft.name.trim() || !draft.headlines.trim() || !draft.descriptions.trim()} onClick={save}>Lưu và dùng mẫu</button>
      </div>
    </details>
    {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
    {notice && <p role="status" className="text-xs text-emerald-700">{notice}</p>}
  </fieldset>;
}
