import React from "react";
import { templateReviewCurrent } from "./win-templates.js";

export default function TemplateApplied({ value, assets }) {
  if (!value) return null;
  const reviewed = templateReviewCurrent(value, assets);
  const edited = value.verification?.status === "reviewed" && !reviewed;
  return <div className="my-3 rounded-lg border border-blue-100 bg-blue-50 p-3 text-sm text-blue-900">
    <p className="font-bold">Đã viết theo mẫu: {value.name}</p>
    <ul className="mt-2 list-inside list-disc">{(value.style_notes || []).map((note, index) => <li key={index}>{note}</li>)}</ul>
    {reviewed && <p className="mt-2 text-xs leading-5">Đã đối chiếu nội dung với {value.verification.source === "manual_brief" ? "thông tin dự án bạn nhập" : "landing page mới và thông tin bạn nhập"}.{value.verification.attempts > 1 ? " AI đã sửa lại bản nháp sau kiểm tra." : ""} Hãy duyệt lại trước khi đăng.</p>}
    {edited && <p className="mt-2 text-xs leading-5 text-amber-800">Nội dung đã thay đổi sau bước đối chiếu AI. Hãy kiểm tra lại bản chỉnh sửa trước khi đăng.</p>}
    {reviewed && value.grounding && <details className="mt-2 text-xs">
      <summary className="cursor-pointer font-bold">Xem thông tin nguồn đã dùng</summary>
      <div className="mt-2 max-h-64 space-y-3 overflow-y-auto">{[...(value.grounding.headlines || []), ...(value.grounding.descriptions || [])].map((asset, index) => <div key={index} className="break-words rounded bg-white p-2"><p className="font-semibold">{asset.text}</p><ul className="mt-1 list-inside list-disc text-slate-600">{(value.facts_used || []).filter(source => asset.fact_ids?.includes(source.id)).map((source, i) => <li key={i}>{source.source.startsWith("landing_page.") ? "Landing page" : "Thông tin bạn nhập"}: {source.text}</li>)}</ul></div>)}</div>
    </details>}
  </div>;
}
