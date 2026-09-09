import React from "react";
import { Upload } from "lucide-react";
import { assetLines, parseWinFile, winDraftIssues, templatePayload } from "./win-templates.js";

const input = "mt-1 w-full min-w-0 rounded-lg border border-slate-200 bg-white p-2 text-sm";
export default function WinTemplateUpload({ request, onSaved, disabled }) {
  const fileInput = React.useRef(null);
  const [rows, setRows] = React.useState([]);
  const [index, setIndex] = React.useState(0);
  const [busy, setBusy] = React.useState(false);
  const [message, setMessage] = React.useState("");
  const [error, setError] = React.useState("");
  const current = rows[index];
  const selected = rows.filter(row => row.selected);
  const issues = current ? winDraftIssues(current) : [];
  const change = (field, value) => setRows(items => items.map((row, i) => i === index ? { ...row, [field]: value } : row));
  async function upload(file) {
    if (!file || busy || disabled) return;
    setBusy(true); setError(""); setMessage("");
    try {
      if (file.size > 5 * 1024 * 1024) throw new Error("File tối đa 5 MB.");
      let drafts;
      if (/\.(csv|xlsx)$/i.test(file.name)) {
        const body = new FormData(); body.append("file", file);
        drafts = (await request("/preview", { method: "POST", body })).drafts.map(row => ({ ...row, headlines: row.headlines.join("\n"), descriptions: row.descriptions.join("\n") }));
      } else {
        drafts = [{ ...parseWinFile(await file.text(), file.name), source: file.name }];
      }
      setRows(drafts.map(row => ({ ...row, selected: true })));
      setIndex(0);
      setMessage(`Đã đọc ${drafts.length} mẫu từ ${file.name}. Chọn và kiểm tra nội dung trước khi lưu.`);
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  async function save() {
    setBusy(true); setError(""); setMessage("");
    try {
      const data = await request("/batch", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(selected.map(templatePayload)) });
      onSaved(data.templates);
      setRows([]); setIndex(0);
      setMessage(`Đã lưu ${data.templates.length} mẫu và chọn mẫu đầu tiên. Bấm tạo RSA để AI viết theo mẫu.`);
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  const sampleCsv = '\uFEFFname,Headline 1,Headline 2,Description 1,Description 2,notes\r\nMẫu lợi ích,Simplify Your Workflow,Explore Acme Today,Keep work organized in one place. Explore Acme today.,Find tools for your team. See features and plans.,Mở đầu bằng lợi ích và kết thúc bằng CTA\r\n';
  return <fieldset disabled={disabled || busy} className="min-w-0 space-y-3">
    <div onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); if (event.dataTransfer.files.length > 1) setError("Chọn một file mỗi lần nhập."); else upload(event.dataTransfer.files[0]); }} className="rounded-lg border-2 border-dashed border-blue-200 bg-white p-4 text-center">
      <Upload size={22} className="mx-auto text-blue-600" />
      <button type="button" className="mt-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-50" onClick={() => fileInput.current?.click()}>{busy ? "Đang xử lý…" : "Chọn file content win từ máy"}</button>
      <input ref={fileInput} aria-label="File content win từ máy" type="file" accept=".xlsx,.csv,.txt,.json" className="sr-only" onChange={event => { upload(event.target.files?.[0]); event.target.value = ""; }} />
      <p className="mt-2 text-xs leading-5 text-slate-600">Hoặc kéo thả file vào đây · Excel (.xlsx), CSV, TXT, JSON · Tối đa 5 MB.</p>
    </div>
    <a className="block text-xs font-bold text-blue-700 underline" download="content-win.csv" href={`data:text/csv;charset=utf-8,${encodeURIComponent(sampleCsv)}`}>Tải file mẫu mở bằng Excel</a>
    <p className="text-xs leading-5 text-slate-600">Excel/CSV: mỗi dòng là một quảng cáo, cột Headline 1–15 và Description 1–4. Chọn file chỉ tạo bản xem trước.</p>
    {message && <p role="status" className="text-xs text-emerald-700">{message}</p>}
    {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
    {current && <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-3">
      <p className="text-sm font-bold">Xem trước · {selected.length}/{rows.length} mẫu đã chọn</p>
      <div className="max-h-44 space-y-2 overflow-y-auto">{rows.map((row, i) => <label key={i} className="flex items-start gap-2 text-xs"><input type="checkbox" checked={row.selected} onChange={event => setRows(items => items.map((item, n) => n === i ? { ...item, selected: event.target.checked } : item))} /><span className="min-w-0 break-words">{row.name || `Mẫu ${i + 1}`} {winDraftIssues(row).length > 0 && <span className="text-red-700">· Cần sửa</span>}</span></label>)}</div>
      <label className="block text-xs font-bold">Mẫu đang xem / sửa<select value={index} onChange={event => setIndex(Number(event.target.value))} className={input}>{rows.map((row, i) => <option key={i} value={i}>{i + 1}. {row.name}</option>)}</select></label>
      <p className="text-xs text-slate-500">Nguồn: {current.source}</p>
      {[["name", "Tên mẫu nhập", 1], ["headlines", "Headlines nhập · mỗi dòng một câu", 4], ["descriptions", "Descriptions nhập · mỗi dòng một câu", 4], ["notes", "Ghi chú mẫu nhập", 2]].map(([field, label, height]) => <label key={field} className="block text-xs font-bold">{label}<textarea className={input} rows={height} value={current[field]} onChange={event => change(field, event.target.value)} />{["headlines", "descriptions"].includes(field) && <span className="font-normal text-slate-500">{assetLines(current[field]).map((line, i) => `${i + 1}: ${[...line].length}/${field === "headlines" ? 30 : 90}`).join(" · ")}</span>}</label>)}
      {issues.length > 0 && <ul className="list-inside list-disc text-xs text-red-700">{issues.map(issue => <li key={issue}>{issue}</li>)}</ul>}
      <button type="button" className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-50" disabled={!selected.length || selected.some(row => winDraftIssues(row).length)} onClick={save}>Lưu {selected.length} mẫu đã chọn</button>
      <button type="button" className="ml-2 text-xs font-bold text-slate-600" onClick={() => setRows([])}>Hủy nhập file</button>
    </div>}
  </fieldset>;
}
