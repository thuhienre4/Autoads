import React from "react";

export default function CampaignTargeting({ value, onChange }) {
  const matches = value.keyword_match_types ?? ["EXACT"];
  return <div className="space-y-3 md:col-span-2">
    <fieldset className="rounded-lg border border-slate-200 p-4">
      <legend className="px-2 text-sm font-bold">Kiểu khớp từ khóa</legend>
      <p className="mb-3 text-xs text-slate-500">Tích một hoặc nhiều kiểu. Có thể dùng cả chính xác và cụm từ.</p>
      <div className="flex flex-wrap gap-3">{[["EXACT", "Khớp chính xác", "[từ khóa]"], ["PHRASE", "Khớp cụm từ", '"từ khóa"'], ["BROAD", "Khớp mở rộng", "từ khóa"]].map(([type, label, example]) => <label key={type} className={`flex cursor-pointer items-start gap-2 rounded-lg border p-3 text-sm ${matches.includes(type) ? "border-blue-300 bg-blue-50" : "border-slate-200"}`}>
        <input type="checkbox" className="mt-1" checked={matches.includes(type)} onChange={event => onChange({ keyword_match_types: event.target.checked ? [...new Set([...matches, type])] : matches.filter(item => item !== type) })} /><span>{label}<span className="mt-1 block text-xs text-slate-500">{example}</span></span>
      </label>)}</div>
      {!matches.length && <p role="alert" className="mt-2 text-xs text-red-700">Chọn ít nhất một kiểu khớp từ khóa.</p>}
    </fieldset>
    <fieldset className="rounded-lg border border-slate-200 p-4">
      <legend className="px-2 text-sm font-bold">Mạng quảng cáo</legend>
      <label className="mb-3 flex items-center gap-2 text-sm text-slate-500"><input type="checkbox" checked disabled />Google Tìm kiếm (luôn bật cho chiến dịch Search)</label>
      <div className="flex flex-wrap gap-4">{[["search_partners", "Đối tác tìm kiếm của Google", true], ["display_network", "Mạng hiển thị Google", false]].map(([key, label, fallback]) => <label key={key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={value[key] ?? fallback} onChange={event => onChange({ [key]: event.target.checked })} />{label}</label>)}</div>
    </fieldset>
  </div>;
}
