import React from "react";
import { createRoot } from "react-dom/client";
import { AlertTriangle, BarChart3, CheckCircle2, Clipboard, Download, FileText, History, Link, Loader2, LogIn, Megaphone, MousePointerClick, Plus, Rocket, Search, ShieldCheck, Sparkles, Trash2, Upload, Zap } from "lucide-react";
import "./styles/index.css";

const apiHost = window.location.hostname || "127.0.0.1";
const apiBase = import.meta.env.VITE_API_BASE_URL || `http://${apiHost}:8000/api/v1`;

const formatNumber = (value) => new Intl.NumberFormat("vi-VN").format(Math.round(value || 0));
const formatMoney = (value, currencyCode = "VND") => new Intl.NumberFormat(
  currencyCode === "USD" ? "en-US" : "vi-VN",
  {
    style: "currency",
    currency: currencyCode,
    maximumFractionDigits: currencyCode === "USD" ? 2 : 0,
  },
).format(Number(value || 0));
const toLines = (value) => value.split("\n").map((item) => item.trim()).filter(Boolean);
const toIsoDateTime = (value) => (value ? new Date(value).toISOString() : null);
const csvCell = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
const safeFilePart = (value) => String(value || "ads")
  .trim()
  .replace(/[^a-z0-9_-]+/gi, "-")
  .replace(/^-+|-+$/g, "") || "ads";
const adsEditorCsvFromPlan = (plan) => {
  const ad = plan?.responsive_search_ad || {};
  const headers = [
    "Campaign", "Ad group", "Ad type", "Status", "Final URL",
    ...Array.from({ length: 15 }, (_, index) => `Headline ${index + 1}`),
    ...Array.from({ length: 4 }, (_, index) => `Description ${index + 1}`),
  ];
  const row = [
    plan?.campaign?.name || "",
    plan?.ad_group?.name || "",
    "Responsive search ad",
    ad.status || "PAUSED",
    ad.final_url || "",
    ...Array.from({ length: 15 }, (_, index) => ad.headlines?.[index] || ""),
    ...Array.from({ length: 4 }, (_, index) => ad.descriptions?.[index] || ""),
  ];
  return [headers, row].map((items) => items.map(csvCell).join(",")).join("\r\n");
};
const parseCsvRow = (row) => {
  const cells = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < row.length; index += 1) {
    const char = row[index];
    const next = row[index + 1];
    if (char === "\"" && quoted && next === "\"") {
      current += "\"";
      index += 1;
    } else if (char === "\"") {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      cells.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  cells.push(current.trim());
  return cells;
};
const splitCsvList = (value) => String(value || "")
  .split(/\r?\n|\s*[|;]\s*/)
  .map((item) => item.trim())
  .filter(Boolean);
const campaignRowsFromCsv = (csvText) => {
  const rows = csvText.split(/\r?\n/).map((row) => row.trim()).filter(Boolean);
  if (rows.length < 2) return [];
  const headers = parseCsvRow(rows[0]).map((cell) => cell.toLowerCase().replace(/^\uFEFF/, "").trim());
  const aliases = {
    landing_page_url: ["landing_page_url", "landing_page", "url", "website", "final_url"],
    product_name: ["product_name", "product", "offer_name", "name"],
    campaign_name: ["campaign_name", "campaign"],
    ad_group_name: ["ad_group_name", "ad_group", "ad group"],
    target_keywords: ["target_keywords", "keywords", "keyword"],
    language: ["language", "ad_language"],
    tone: ["tone", "campaign_tone"],
    target_audience: ["target_audience", "audience"],
    primary_offer: ["primary_offer", "offer"],
    primary_cta: ["primary_cta", "cta"],
    trust_signals: ["trust_signals", "trust"],
    daily_budget_vnd: ["daily_budget_vnd", "daily_budget", "budget"],
    manual_cpc_bid_vnd: ["manual_cpc_bid_vnd", "manual_cpc", "cpc_bid", "cpc"],
    currency_code: ["currency_code", "currency"],
    target_location: ["target_location", "location", "country"],
    excluded_locations: ["excluded_locations", "exclude_locations"],
    excluded_location_ids: ["excluded_location_ids", "exclude_location_ids"],
    customer_ids: ["customer_ids", "customer_id", "account_ids", "account_id"],
    schedule_enabled: ["schedule_enabled", "scheduled"],
    scheduled_at: ["scheduled_at", "publish_at", "publish_time"],
    schedule_timezone: ["schedule_timezone", "timezone"],
  };
  const indexes = Object.fromEntries(Object.entries(aliases).map(([field, names]) => [
    field,
    headers.findIndex((header) => names.includes(header)),
  ]));
  if (indexes.landing_page_url < 0) return [];
  return rows.slice(1, 51).map((row, index) => {
    const cells = parseCsvRow(row);
    const value = (field) => indexes[field] >= 0 ? String(cells[indexes[field]] || "").trim() : "";
    const landingPageUrl = normalizeProjectUrl(value("landing_page_url"));
    const currency = value("currency_code").toUpperCase();
    const customerIds = String(value("customer_ids") || "").split(/\s*[,|;]\s*/)
      .map((item) => item.replace(/\D/g, ""))
      .filter(Boolean);
    const errors = [];
    if (!landingPageUrl) errors.push("Thiếu landing page URL hợp lệ");
    if (currency && !["VND", "USD"].includes(currency)) errors.push("Currency chỉ hỗ trợ VND hoặc USD");
    return {
      rowNumber: index + 2,
      landing_page_url: landingPageUrl,
      product_name: value("product_name"),
      campaign_name: value("campaign_name"),
      ad_group_name: value("ad_group_name"),
      target_keywords: splitCsvList(value("target_keywords")).join("\n"),
      language: value("language"),
      tone: value("tone"),
      target_audience: value("target_audience"),
      primary_offer: value("primary_offer"),
      primary_cta: value("primary_cta"),
      trust_signals: value("trust_signals"),
      daily_budget_vnd: value("daily_budget_vnd"),
      manual_cpc_bid_vnd: value("manual_cpc_bid_vnd"),
      currency_code: currency,
      target_location: value("target_location"),
      excluded_locations: splitCsvList(value("excluded_locations")).join("\n"),
      excluded_location_ids: splitCsvList(value("excluded_location_ids")).join("\n"),
      customer_ids: [...new Set(customerIds)],
      schedule_enabled: ["1", "true", "yes", "on"].includes(value("schedule_enabled").toLowerCase()),
      scheduled_at: value("scheduled_at"),
      schedule_timezone: value("schedule_timezone") || "Asia/Saigon",
      errors,
    };
  });
};
const normalizeProjectUrl = (value) => {
  const text = String(value || "").trim();
  if (!text) return "";
  if (!/[./]/.test(text) && !/^https?:\/\//i.test(text)) return "";
  return /^https?:\/\//i.test(text) ? text : `https://${text}`;
};
const projectsFromCsv = (csvText) => {
  const rows = csvText.split(/\r?\n/).map((row) => row.trim()).filter(Boolean);
  if (!rows.length) return [];
  const first = parseCsvRow(rows[0]).map((cell) => cell.toLowerCase().replace(/^\uFEFF/, ""));
  const hasHeader = first.some((cell) => ["name", "project", "title", "url", "domain", "website", "link"].includes(cell));
  const headers = hasHeader ? first : [];
  const bodyRows = hasHeader ? rows.slice(1) : rows;
  const findIndex = (names, fallback) => {
    const index = headers.findIndex((header) => names.includes(header));
    return index >= 0 ? index : fallback;
  };
  const nameIndex = findIndex(["name", "project", "title", "product"], 0);
  const urlIndex = findIndex(["url", "domain", "website", "link"], hasHeader ? 1 : 0);
  return bodyRows
    .map((row, index) => {
      const cells = parseCsvRow(row);
      const rawUrl = normalizeProjectUrl(cells[urlIndex] || cells[0]);
      const name = cells[nameIndex] || cells[0] || `Project ${index + 1}`;
      return rawUrl ? { name, url: rawUrl, source: "csv_upload", customer_ids: [] } : null;
    })
    .filter(Boolean);
};
const countCsvRowsMissingUrl = (csvText) => {
  const rows = csvText.split(/\r?\n/).map((row) => row.trim()).filter(Boolean);
  if (!rows.length) return 0;
  const first = parseCsvRow(rows[0]).map((cell) => cell.toLowerCase().replace(/^\uFEFF/, ""));
  const hasHeader = first.some((cell) => ["name", "project", "title", "url", "domain", "website", "link"].includes(cell));
  const headers = hasHeader ? first : [];
  const bodyRows = hasHeader ? rows.slice(1) : rows;
  const urlIndex = headers.findIndex((header) => ["url", "domain", "website", "link"].includes(header));
  return bodyRows.filter((row) => {
    const cells = parseCsvRow(row);
    const rawUrl = urlIndex >= 0 ? cells[urlIndex] : cells[1] || cells[0];
    return !normalizeProjectUrl(rawUrl);
  }).length;
};
const projectNamesFromText = (value) => value
  .split(/\r?\n|,/)
  .map((item) => item.trim())
  .filter(Boolean)
  .slice(0, 50);
const affiliateResearchToCsv = (report) => {
  const escapeCell = (value) => `"${String(value ?? "").replace(/"/g, "\"\"")}"`;
  const rows = [["project_name", "official_domain", "official_url", "signup_url", "signup_confidence", "status", "confidence", "affiliate_url", "matched_terms", "top_candidates"]];
  (report?.items || []).forEach((item) => {
    rows.push([
      item.project_name,
      item.official_domain || "",
      item.official_url || "",
      item.signup_url || "",
      item.signup_confidence || 0,
      item.status,
      item.confidence,
      item.affiliate_url || "",
      (item.matched_terms || []).join(", "),
      (item.candidates || []).slice(0, 3).map((candidate) => candidate.url).join(" | "),
    ]);
  });
  return rows.map((row) => row.map(escapeCell).join(",")).join("\n");
};
const affiliateResearchError = (report) => {
  if (!report) return "";
  if (report.error) return report.error;
  const failedItem = (report.items || []).find((item) => item.status === "error" && item.error);
  return failedItem?.error || "";
};
const normalizeAssets = (assets) => ({
  ...assets,
  headlines: (assets?.headlines || []).map((item) => item.trim()).filter(Boolean).slice(0, 15),
  descriptions: (assets?.descriptions || []).map((item) => item.trim()).filter(Boolean).slice(0, 4),
});
const normalizeDuplicateText = (value) => String(value || "")
  .normalize("NFKC")
  .toLocaleLowerCase()
  .replace(/[^\p{L}\p{N}]+/gu, " ")
  .trim();
const duplicateAssetIndexes = (items = []) => {
  const indexesByValue = new Map();
  items.forEach((item, index) => {
    const normalized = normalizeDuplicateText(item);
    if (!normalized) return;
    indexesByValue.set(normalized, [...(indexesByValue.get(normalized) || []), index]);
  });
  return new Set(
    [...indexesByValue.values()]
      .filter((indexes) => indexes.length > 1)
      .flat(),
  );
};
const accountStatusPresentation = (account = {}) => {
  const status = String(account.status || "NOT_SYNCED").toUpperCase();
  const presentations = {
    ENABLED: { label: "Active", badge: "border-emerald-200 bg-emerald-50 text-emerald-700", dot: "bg-emerald-500" },
    CANCELED: { label: "Canceled", badge: "border-amber-200 bg-amber-50 text-amber-700", dot: "bg-amber-500" },
    SUSPENDED: { label: "Suspended", badge: "border-red-200 bg-red-50 text-red-700", dot: "bg-red-500" },
    CLOSED: { label: "Closed", badge: "border-slate-300 bg-slate-100 text-slate-600", dot: "bg-slate-500" },
    NOT_SYNCED: { label: "Not synced", badge: "border-blue-200 bg-blue-50 text-blue-700", dot: "bg-blue-400" },
  };
  return presentations[status] || { label: account.status_label || "Unknown", badge: "border-slate-200 bg-white text-slate-600", dot: "bg-slate-400" };
};

function AccountStatusBadge({ account }) {
  const presentation = accountStatusPresentation(account);
  return (
    <span
      title={account.status_description || presentation.label}
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-1 text-[10px] font-black uppercase tracking-wide ${presentation.badge}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${presentation.dot}`} />
      {account.status_label || presentation.label}
    </span>
  );
}
const formatApiErrorDetail = (detail) => {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.join("\n");
  const accounts = detail?.accounts;
  if (!Array.isArray(accounts)) return JSON.stringify(detail);
  return accounts.map((account) => {
    const messages = (account.errors || []).map((item) => {
      const topics = (item.policy_topic_entries || [])
        .map((entry) => `${entry.topic || "Unknown policy"} (${entry.type_ || "policy"})`)
        .join(", ");
      return topics ? `${item.message} Policy: ${topics}.` : item.message;
    }).filter(Boolean);
    return `Customer ${account.customer_id}: ${messages.join(" ") || "Google Ads rejected the request."}`;
  }).join("\n");
};
const navItems = [
  { id: "content", label: "Content", icon: Sparkles },
  { id: "deploy", label: "Publish", icon: Rocket },
  { id: "automation", label: "Auto", icon: Zap },
  { id: "affiliate", label: "Links", icon: Link },
  { id: "history", label: "History", icon: History },
];

async function postApi(path, payload) {
  const response = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const detail = errorData.detail || "Request failed";
    throw new Error(formatApiErrorDetail(detail));
  }
  return response.json();
}

function useApi(path, initialValue, refreshMs = 0) {
  const [data, setData] = React.useState(initialValue);
  React.useEffect(() => {
    let active = true;
    const load = () => fetch(`${apiBase}${path}`)
      .then((response) => (response.ok ? response.json() : Promise.reject(response)))
      .then((value) => active && setData(value))
      .catch(() => active && setData(initialValue));
    load();
    const timer = refreshMs > 0 ? window.setInterval(load, refreshMs) : null;
    return () => {
      active = false;
      if (timer) window.clearInterval(timer);
    };
  }, [path, refreshMs]);
  return data;
}

function Field({ label, children, wide = false }) {
  return (
    <label className={`space-y-2 text-xs font-bold uppercase text-slate-500 ${wide ? "md:col-span-2" : ""}`}>
      {label}
      {children}
    </label>
  );
}

function StatusTile({ icon: Icon, label, value, tone = "slate" }) {
  const tones = {
    slate: "status-tile--slate",
    blue: "status-tile--blue",
    emerald: "status-tile--emerald",
    amber: "status-tile--amber",
  };
  return (
    <div className={`status-tile ${tones[tone] || tones.slate}`}>
      <div className="flex items-center gap-3">
        <div className="status-tile__icon">
          <Icon size={16} />
        </div>
        <div className="min-w-0">
          <p className="text-[10px] font-black uppercase tracking-[0.13em] text-slate-500">{label}</p>
          <p className="mt-0.5 truncate text-sm font-black text-slate-950">{value}</p>
        </div>
      </div>
    </div>
  );
}

function WorkspaceOverview({ accountStatus, selectedCustomerIds, generated }) {
  return (
    <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4" aria-label="Workspace status">
      <StatusTile
        icon={ShieldCheck}
        label="Google Ads"
        value={accountStatus.can_publish_live ? "Live publish ready" : "Draft validation only"}
        tone={accountStatus.can_publish_live ? "emerald" : "amber"}
      />
      <StatusTile
        icon={Megaphone}
        label="MCC Manager"
        value={accountStatus.login_customer_id || "Not connected"}
        tone="slate"
      />
      <StatusTile
        icon={Rocket}
        label="Selected Accounts"
        value={selectedCustomerIds.length
          ? `${selectedCustomerIds.length} of ${accountStatus.accounts?.length || selectedCustomerIds.length} accounts`
          : "Choose account"}
        tone="blue"
      />
      <StatusTile
        icon={BarChart3}
        label="Creative Draft"
        value={generated ? `${generated.headlines?.length || 0} headlines, ${generated.descriptions?.length || 0} descriptions` : "No draft yet"}
        tone="slate"
      />
    </section>
  );
}

function ExtractionSummary({ generated }) {
  const page = generated?.landing_page_alignment?.page_context;
  if (!page) return null;
  const confidence = Number(page.extraction_confidence || 0);
  const signalGroups = [
    ["Key features", page.key_features || []],
    ["Customer benefits", page.customer_benefits || []],
    ["Offers", page.detected_offers || []],
    ["CTAs", page.detected_ctas || []],
    ["Trust signals", page.detected_trust_signals || []],
  ];
  return (
    <div className="mb-5 rounded-xl border border-blue-200 bg-gradient-to-br from-blue-50 to-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.16em] text-blue-700">Content intelligence report</p>
          <p className="mt-1 max-w-xl truncate text-sm font-black text-slate-950">{page.title || page.final_url || "Landing page"}</p>
        </div>
        <div className="flex gap-2">
          <span className="rounded-full border border-violet-200 bg-white px-3 py-1.5 text-xs font-black text-violet-700">
            {page.fetch_method === "playwright" ? "Browser rendered" : "HTTP"}
          </span>
          <span className="rounded-full border border-blue-200 bg-white px-3 py-1.5 text-xs font-black text-blue-700">{confidence}% confidence</span>
          <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-600">{page.word_count || 0} words</span>
        </div>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {signalGroups.map(([label, items]) => (
          <div key={label} className="rounded-lg border border-blue-100 bg-white/85 p-3">
            <p className="text-[10px] font-black uppercase tracking-[0.12em] text-slate-500">{label}</p>
            <p className="mt-1 line-clamp-2 text-xs font-semibold leading-5 text-slate-700">
              {items.length ? items.slice(0, 2).join(" · ") : "Not detected"}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function AssetRow({ children }) {
  const copy = () => navigator.clipboard?.writeText(children);
  return (
    <div className="flex items-center gap-2">
      <div className="min-h-10 flex-1 rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-900">
        {children}
      </div>
      <button onClick={copy} className="grid h-10 w-10 place-items-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-blue-300 hover:text-blue-700" title="Copy">
        <Clipboard size={16} />
      </button>
    </div>
  );
}

function EditableAssetRow({ value, maxLength, multiline = false, duplicate = false, onChange, onDelete }) {
  const copy = () => navigator.clipboard?.writeText(value);
  const overLimit = value.length > maxLength;
  const Input = multiline ? "textarea" : "input";
  const inputTone = overLimit
    ? "border-red-300 focus:border-red-500 focus:ring-red-100"
    : duplicate
      ? "border-amber-400 focus:border-amber-500 focus:ring-amber-100"
      : "border-slate-200 focus:border-blue-500 focus:ring-blue-100";

  return (
    <div className={`rounded-lg border p-3 ${duplicate ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-slate-50"}`}>
      <div className="flex items-start gap-2">
        <Input
          className={`min-h-10 flex-1 resize-y rounded-lg border bg-white px-3 py-2 text-sm font-semibold text-slate-950 outline-none transition focus:ring-2 ${inputTone}`}
          maxLength={maxLength + 20}
          rows={multiline ? 3 : undefined}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
        <button onClick={copy} className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-blue-300 hover:text-blue-700" title="Copy">
          <Clipboard size={16} />
        </button>
        <button onClick={onDelete} className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-red-300 hover:text-red-700" title="Delete">
          <Trash2 size={16} />
        </button>
      </div>
      <div className="mt-2 flex items-center justify-between gap-3">
        {duplicate ? (
          <span className="inline-flex items-center gap-1 text-xs font-bold text-amber-700">
            <AlertTriangle size={13} /> Trùng nội dung
          </span>
        ) : <span />}
        <span className={`text-xs font-bold ${overLimit ? "text-red-600" : "text-slate-400"}`}>
          {value.length}/{maxLength}
        </span>
      </div>
    </div>
  );
}

function CreativeAssets({ generated, onChange }) {
  if (!generated) {
    return (
      <section id="creative-assets" className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center">
        <Sparkles className="mx-auto text-blue-600" size={28} />
        <h2 className="mt-4 text-lg font-bold text-slate-950">Final Creative Assets</h2>
        <p className="mt-2 text-sm text-slate-500">Generate content from a landing page URL to preview English RSA assets here.</p>
      </section>
    );
  }

  const updateAsset = (type, index, value) => {
    const nextItems = [...generated[type]];
    nextItems[index] = value;
    onChange({ ...generated, [type]: nextItems });
  };
  const deleteAsset = (type, index) => {
    onChange({ ...generated, [type]: generated[type].filter((_, itemIndex) => itemIndex !== index) });
  };
  const addAsset = (type) => {
    const limit = type === "headlines" ? 15 : 4;
    if (generated[type].length >= limit) return;
    onChange({ ...generated, [type]: [...generated[type], ""] });
  };
  const seo = generated.seo_analysis || {};
  const copySeoPlan = () => {
    const actions = (seo.improvement_plan || []).map(
      (item, index) => `${index + 1}. [${item.priority.toUpperCase()}] ${item.area}: ${item.action} (+${item.estimated_gain})`,
    );
    navigator.clipboard?.writeText([
      `SEO score: ${seo.score || 0}/100`,
      `Potential score: ${seo.potential_score || seo.score || 0}/100`,
      "",
      ...actions,
    ].join("\n"));
  };
  const duplicateHeadlines = duplicateAssetIndexes(generated.headlines);
  const duplicateDescriptions = duplicateAssetIndexes(generated.descriptions);
  const duplicateCount = duplicateHeadlines.size + duplicateDescriptions.size;

  return (
    <section id="creative-assets" className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-5">
        <div>
          <h2 className="text-lg font-bold text-slate-950">Final Creative Assets</h2>
          <p className="mt-1 text-sm text-slate-500">Edit headlines and descriptions here before validating or publishing.</p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-xs font-bold uppercase tracking-[0.14em] text-emerald-700">
          <ShieldCheck size={14} /> Editable Draft
        </span>
      </div>

      {duplicateCount > 0 && (
        <div className="mt-5 flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-800">
          <AlertTriangle className="mt-0.5 shrink-0" size={18} />
          <div>
            <p className="text-sm font-black">Phát hiện nội dung trùng lặp</p>
            <p className="mt-1 text-xs font-semibold leading-5">
              Có {duplicateHeadlines.size} headline và {duplicateDescriptions.size} description bị trùng. Các ô liên quan đã được đánh dấu để bạn chỉnh sửa trước khi đăng.
            </p>
          </div>
        </div>
      )}

      {seo.score !== undefined && (
        <div className="mt-5 rounded-lg border border-blue-200 bg-blue-50 p-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-wide text-blue-700">SEO & Message Match</p>
              <div className="mt-2 flex items-end gap-2">
                <span className="text-3xl font-black text-slate-950">{seo.score}</span>
                <span className="pb-1 text-sm font-bold text-slate-500">/100 · {seo.grade}</span>
              </div>
              {seo.potential_score > seo.score && (
                <p className="mt-1 text-xs font-bold text-emerald-700">Potential after fixes: {seo.potential_score}/100</p>
              )}
            </div>
            <div className="flex flex-col items-end gap-2 text-right text-xs font-bold text-slate-600">
              <div>
                <p>Intent: <span className="capitalize text-slate-950">{seo.search_intent}</span></p>
                <p className="mt-1">Primary: <span className="text-slate-950">{seo.primary_keyword || "—"}</span></p>
              </div>
              <button type="button" onClick={copySeoPlan} className="inline-flex items-center gap-1.5 rounded-lg border border-blue-200 bg-white px-3 py-2 text-xs font-black text-blue-700 hover:border-blue-400">
                <Clipboard size={13} /> Copy improvement plan
              </button>
            </div>
          </div>
          {seo.subscores && (
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {[
                ["Landing page", seo.subscores.landing_page],
                ["Keyword alignment", seo.subscores.keyword_alignment],
                ["RSA quality", seo.subscores.rsa_quality],
                ["Conversion", seo.subscores.conversion_readiness],
              ].map(([label, value]) => (
                <div key={label} className="rounded-lg border border-blue-100 bg-white p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-bold text-slate-500">{label}</p>
                    <p className="text-sm font-black text-slate-950">{value ?? 0}</p>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div className={`h-full rounded-full ${(value || 0) >= 80 ? "bg-emerald-500" : (value || 0) >= 60 ? "bg-blue-500" : "bg-amber-500"}`} style={{ width: `${Math.min(100, value || 0)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            {[
              ["Headline keywords", seo.headline_keyword_coverage],
              ["Description keywords", seo.description_keyword_coverage],
              ["Landing page match", seo.landing_page_keyword_coverage],
            ].map(([label, value]) => (
              <div key={label} className="rounded-md border border-blue-100 bg-white p-3">
                <p className="text-xs font-bold text-slate-500">{label}</p>
                <p className="mt-1 text-lg font-black text-slate-950">{value ?? 0}%</p>
              </div>
            ))}
          </div>
          {(seo.improvement_plan || []).length > 0 && (
            <div className="mt-4 border-t border-blue-200 pt-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <p className="text-xs font-black uppercase tracking-[0.12em] text-slate-700">Priority improvement plan</p>
                <span className="text-xs font-bold text-slate-500">{seo.improvement_plan.length} actions</span>
              </div>
              <div className="grid gap-2 lg:grid-cols-2">
                {seo.improvement_plan.slice(0, 8).map((item, index) => {
                  const tone = item.priority === "critical"
                    ? "border-red-200 bg-red-50 text-red-700"
                    : item.priority === "high"
                      ? "border-amber-200 bg-amber-50 text-amber-700"
                      : "border-blue-100 bg-white text-blue-700";
                  return (
                    <div key={`${item.area}-${index}`} className={`rounded-lg border p-3 ${tone}`}>
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-[10px] font-black uppercase tracking-[0.12em]">{item.priority} · {item.area}</p>
                        <span className="rounded-full bg-white/80 px-2 py-1 text-[10px] font-black">+{item.estimated_gain}</span>
                      </div>
                      <p className="mt-1 text-xs font-semibold leading-5 text-slate-700">{item.action}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {(seo.checks || []).map((check) => (
              <p key={check.label} className={`text-xs font-bold ${check.passed ? "text-emerald-700" : "text-amber-700"}`}>
                {check.passed ? "✓" : "!"} {check.label}
              </p>
            ))}
          </div>
          {(seo.recommendations || []).length > 0 && !(seo.improvement_plan || []).length && (
            <ul className="mt-4 space-y-1 border-t border-blue-200 pt-3 text-xs font-semibold leading-5 text-slate-600">
              {seo.recommendations.map((item) => <li key={item}>• {item}</li>)}
            </ul>
          )}
        </div>
      )}

      <div className="mt-6 space-y-8">
        <div>
          <div className="mb-4 flex items-center justify-between">
            <p className="text-xs font-bold uppercase text-slate-500">Responsive Headlines (30 max)</p>
            <button onClick={() => addAsset("headlines")} disabled={generated.headlines.length >= 15} className="inline-flex h-8 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-bold text-slate-700 hover:border-blue-300 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
              <Plus size={14} /> {generated.headlines.length}/15
            </button>
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            {generated.headlines.map((headline, index) => (
              <EditableAssetRow
                key={`headline-${index}`}
                value={headline}
                maxLength={30}
                duplicate={duplicateHeadlines.has(index)}
                onChange={(value) => updateAsset("headlines", index, value)}
                onDelete={() => deleteAsset("headlines", index)}
              />
            ))}
          </div>
        </div>

        <div>
          <div className="mb-4 flex items-center justify-between">
            <p className="text-xs font-bold uppercase text-slate-500">Responsive Descriptions (90 max)</p>
            <button onClick={() => addAsset("descriptions")} disabled={generated.descriptions.length >= 4} className="inline-flex h-8 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-bold text-slate-700 hover:border-blue-300 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
              <Plus size={14} /> {generated.descriptions.length}/4
            </button>
          </div>
          <div className="space-y-3">
            {generated.descriptions.map((description, index) => (
              <EditableAssetRow
                key={`description-${index}`}
                value={description}
                maxLength={90}
                multiline
                duplicate={duplicateDescriptions.has(index)}
                onChange={(value) => updateAsset("descriptions", index, value)}
                onDelete={() => deleteAsset("descriptions", index)}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function GoogleAdsConnectionBanner({ accountStatus, onConnect }) {
  const isConnected = Boolean(
    accountStatus.google_oauth_logged_in &&
    accountStatus.google_ads_scope_granted &&
    accountStatus.refresh_token_available
  );

  if (isConnected) {
    return (
    <section className="rounded-lg border border-emerald-200 bg-white px-5 py-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-lg bg-emerald-600 text-white">
              <CheckCircle2 size={18} />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-black text-slate-950">Google Ads Gmail Connected</p>
              <p className="break-words text-sm font-semibold text-slate-600">
                {accountStatus.google_user?.email || "Google Ads OAuth is ready"} · Client ID {accountStatus.customer_id || "not set"}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-black uppercase text-blue-700">
              MCC auto-sync · 30s
            </span>
            <span className="rounded-full border border-emerald-300 bg-emerald-50 px-4 py-2 text-xs font-black uppercase text-emerald-700">
              {accountStatus.can_publish_live ? "Live Ready" : "Draft Ready"}
            </span>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-amber-200 bg-white px-5 py-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-lg bg-amber-500 text-white">
            <LogIn size={18} />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-black text-amber-950">Connect Gmail Google Ads Account</p>
            <p className="break-words text-sm font-semibold text-amber-800">
              Login with the MCC Gmail once to enable automatic account discovery, campaign validation and live publish.
            </p>
          </div>
        </div>
        <button onClick={onConnect} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 py-2 text-sm font-bold text-white hover:bg-blue-700">
          <LogIn size={16} /> Connect Google Ads
        </button>
      </div>
    </section>
  );
}

function AffiliateWrapper({ inputClass, primaryButton, onUseProject }) {
  const [form, setForm] = React.useState({
    url: "https://www.amazon.com/dp/B08N5WRWNW",
    sub_id: "content-tool",
    campaign: "rsa-architect",
    public_base_url: "",
    use_redirect_tracking: false,
    shorten: false,
  });
  const [result, setResult] = React.useState(null);
  const [stats, setStats] = React.useState(null);
  const [projectScan, setProjectScan] = React.useState(null);
  const [includeUnmatched, setIncludeUnmatched] = React.useState(false);
  const [projectNameSearch, setProjectNameSearch] = React.useState("Amazon");
  const [projectNameResult, setProjectNameResult] = React.useState(null);
  const [csvText, setCsvText] = React.useState("name,url\nTradingView,https://tradingview.com\nKoinly,https://koinly.io");
  const [csvFileName, setCsvFileName] = React.useState("");
  const [researchNames, setResearchNames] = React.useState("TradingView\nKoinly\nCoinLedger");
  const [researchReport, setResearchReport] = React.useState(null);
  const [researchReportKey, setResearchReportKey] = React.useState("");
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [scanLoading, setScanLoading] = React.useState(false);
  const [researchLoading, setResearchLoading] = React.useState(false);
  const currentResearchNames = projectNamesFromText(researchNames);
  const currentResearchKey = currentResearchNames.map((name) => name.toLowerCase()).join("\n");
  const visibleResearchReport = currentResearchNames.length && researchReportKey === currentResearchKey ? researchReport : null;

  const wrapLink = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    setStats(null);
    try {
      setResult(await postApi("/affiliate/wrap", form));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    if (!result?.short_code) return;
    setError("");
    try {
      const response = await fetch(`${apiBase}/affiliate/stats/${result.short_code}`);
      if (!response.ok) throw new Error("Stats not found");
      setStats(await response.json());
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const scanProjects = async () => {
    setScanLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/affiliate/projects/scan?include_unmatched=${includeUnmatched}`);
      if (!response.ok) throw new Error("Cannot scan affiliate projects");
      setProjectScan(await response.json());
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setScanLoading(false);
    }
  };

  const scanGoogleAdsProjects = async () => {
    setScanLoading(true);
    setError("");
    try {
      const name = projectNameSearch.trim();
      const params = new URLSearchParams({
        include_unmatched: String(includeUnmatched),
      });
      if (name) params.set("project_name", name);
      const response = await fetch(`${apiBase}/affiliate/projects/scan-google-ads?${params.toString()}`);
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Cannot scan Google Ads projects");
      }
      setProjectScan(await response.json());
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setScanLoading(false);
    }
  };

  const searchProjectsByName = async () => {
    const name = projectNameSearch.trim();
    if (!name) {
      setError("Enter a project name to filter.");
      return;
    }
    setScanLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/affiliate/projects/search?project_name=${encodeURIComponent(name)}&include_unmatched=${includeUnmatched}`);
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Cannot filter projects by name");
      }
      setProjectNameResult(await response.json());
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setScanLoading(false);
    }
  };

  const scanCsvProjects = async () => {
    const projects = projectsFromCsv(csvText);
    if (!projects.length) {
      setError("CSV needs at least one project URL or domain.");
      return;
    }
    setScanLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/affiliate/projects/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ projects, include_unmatched: includeUnmatched }),
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Cannot scan CSV affiliate projects");
      }
      setProjectScan(await response.json());
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setScanLoading(false);
    }
  };

  const loadCsvFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setCsvFileName(file.name);
    setCsvText(await file.text());
  };

  const runAffiliateResearch = async () => {
    const projectNames = projectNamesFromText(researchNames);
    const reportKey = projectNames.map((name) => name.toLowerCase()).join("\n");
    if (!projectNames.length) {
      setResearchReport(null);
      setResearchReportKey("");
      setError("Enter at least one project name.");
      return;
    }
    setResearchLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/affiliate/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_names: projectNames, max_results: 5 }),
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Cannot run affiliate research");
      }
      const report = await response.json();
      setResearchReport(report);
      setResearchReportKey(reportKey);
      const reportError = affiliateResearchError(report);
      if (reportError) setError(reportError);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setResearchLoading(false);
    }
  };

  const scanPublicGoogleProject = async () => {
    const name = projectNameSearch.trim();
    if (!name) {
      setError("Enter a project name to scan public Google results.");
      return;
    }
    const reportKey = name.toLowerCase();
    setResearchLoading(true);
    setError("");
    setResearchNames(name);
    try {
      const response = await fetch(`${apiBase}/affiliate/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_names: [name], max_results: 5 }),
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Cannot scan public Google results");
      }
      const report = await response.json();
      setResearchReport(report);
      setResearchReportKey(reportKey);
      const reportError = affiliateResearchError(report);
      if (reportError) setError(reportError);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setResearchLoading(false);
    }
  };

  const downloadResearchCsv = () => {
    if (!researchReport) return;
    const blob = new Blob([affiliateResearchToCsv(researchReport)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `affiliate-research-${researchReport.id || "report"}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const copy = (value) => navigator.clipboard?.writeText(value || "");
  const useProject = (project) => {
    setForm((current) => ({
      ...current,
      url: project.url,
      campaign: project.name || current.campaign,
    }));
    onUseProject?.(project);
  };

  return (
    <section className="grid gap-6 lg:grid-cols-[410px_1fr]">
      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-6 flex items-center gap-2">
          <Link className="text-blue-600" size={18} />
          <h2 className="text-sm font-black uppercase">Affiliate Link Wrapper</h2>
        </div>
        <div className="space-y-4">
          <Field label="Original URL" wide>
            <input className={inputClass} value={form.url} onChange={(event) => setForm({ ...form, url: event.target.value })} />
          </Field>
          <Field label="Sub ID">
            <input className={inputClass} value={form.sub_id} onChange={(event) => setForm({ ...form, sub_id: event.target.value })} />
          </Field>
          <Field label="Campaign">
            <input className={inputClass} value={form.campaign} onChange={(event) => setForm({ ...form, campaign: event.target.value })} />
          </Field>
          <Field label="Public Tracking Domain">
            <input className={inputClass} placeholder="https://go.yourdomain.com" value={form.public_base_url} onChange={(event) => setForm({ ...form, public_base_url: event.target.value })} />
          </Field>
          <label className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-bold text-slate-700">
            <input type="checkbox" checked={form.use_redirect_tracking || form.shorten} onChange={(event) => setForm({ ...form, use_redirect_tracking: event.target.checked })} disabled={form.shorten} />
            Enable redirect tracking
          </label>
          <label className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-bold text-slate-700">
            <input type="checkbox" checked={form.shorten} onChange={(event) => setForm({ ...form, shorten: event.target.checked, use_redirect_tracking: event.target.checked ? true : form.use_redirect_tracking })} />
            Shorten tracking link
          </label>
          <button onClick={wrapLink} disabled={loading} className={`${primaryButton} w-full`}>
            {loading ? <Loader2 className="animate-spin" size={16} /> : <Sparkles size={16} />} Generate Affiliate Link
          </button>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-black text-slate-950">Affiliate Project Filter</p>
                <p className="mt-1 text-xs font-semibold text-slate-500">Scan publish history or CSV rows and detect configured affiliate programs.</p>
              </div>
            </div>
            <Field label="Project Name">
              <div className="flex gap-2">
                <input
                  className={inputClass}
                  value={projectNameSearch}
                  onChange={(event) => setProjectNameSearch(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") searchProjectsByName();
                  }}
                  placeholder="Amazon, Shopee, WPManageNinja"
                />
                <button
                  onClick={searchProjectsByName}
                  disabled={scanLoading}
                  className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-slate-950 text-white hover:bg-blue-700 disabled:opacity-60"
                  title="Filter by project name"
                >
                  {scanLoading ? <Loader2 className="animate-spin" size={16} /> : <Search size={16} />}
                </button>
              </div>
            </Field>
            <label className="mb-3 flex items-center gap-3 text-sm font-bold text-slate-700">
              <input type="checkbox" checked={includeUnmatched} onChange={(event) => setIncludeUnmatched(event.target.checked)} />
              Show unmatched projects
            </label>
            <button onClick={scanProjects} disabled={scanLoading} className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 hover:border-blue-300 hover:text-blue-700 disabled:opacity-60">
              {scanLoading ? <Loader2 className="animate-spin" size={16} /> : <BarChart3 size={16} />} Scan Projects
            </button>
            <button onClick={scanGoogleAdsProjects} disabled={scanLoading} className="mt-2 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 py-2 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-60">
              {scanLoading ? <Loader2 className="animate-spin" size={16} /> : <ShieldCheck size={16} />} Scan Google Ads Live
            </button>
            <button onClick={scanPublicGoogleProject} disabled={researchLoading} className="mt-2 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-bold text-emerald-800 hover:border-emerald-400 disabled:opacity-60">
              {researchLoading ? <Loader2 className="animate-spin" size={16} /> : <Search size={16} />} Scan Public Google
            </button>
          </div>
          <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-black text-blue-950">CSV Affiliate Scanner</p>
                <p className="mt-1 text-xs font-semibold leading-5 text-blue-800">Upload or paste CSV with name,url columns. Domains without https:// are normalized automatically.</p>
              </div>
              <FileText className="shrink-0 text-blue-700" size={18} />
            </div>
            <label className="mb-3 flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-lg border border-blue-200 bg-white px-4 py-2 text-sm font-bold text-blue-800 hover:border-blue-400">
              <Upload size={16} />
              {csvFileName || "Choose CSV File"}
              <input type="file" accept=".csv,text/csv" className="hidden" onChange={loadCsvFile} />
            </label>
            <textarea
              className="min-h-32 w-full resize-y rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm font-semibold text-slate-950 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              value={csvText}
              onChange={(event) => setCsvText(event.target.value)}
            />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-bold text-blue-800">
                {projectsFromCsv(csvText).length} rows ready · {countCsvRowsMissingUrl(csvText)} missing URL
              </span>
              <button onClick={scanCsvProjects} disabled={scanLoading} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-60">
                {scanLoading ? <Loader2 className="animate-spin" size={16} /> : <BarChart3 size={16} />} Scan CSV
              </button>
            </div>
          </div>
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-black text-emerald-950">Public Google Affiliate Research</p>
                <p className="mt-1 text-xs font-semibold leading-5 text-emerald-800">Paste project names. The backend searches public Google results, checks affiliate keywords, and builds a report.</p>
              </div>
              <Search className="shrink-0 text-emerald-700" size={18} />
            </div>
            <textarea
              className="min-h-36 w-full resize-y rounded-lg border border-emerald-200 bg-white px-3 py-2 text-sm font-semibold text-slate-950 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              value={researchNames}
              onChange={(event) => {
                const nextValue = event.target.value;
                const nextNames = projectNamesFromText(nextValue);
                const nextKey = nextNames.map((name) => name.toLowerCase()).join("\n");
                setResearchNames(nextValue);
                if (!nextNames.length || nextKey !== researchReportKey) {
                  setResearchReport(null);
                  setResearchReportKey("");
                }
              }}
              placeholder="One project name per line"
            />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-bold text-emerald-800">{currentResearchNames.length} names ready</span>
              <button onClick={runAffiliateResearch} disabled={researchLoading || !currentResearchNames.length} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-bold text-white hover:bg-emerald-700 disabled:opacity-60">
                {researchLoading ? <Loader2 className="animate-spin" size={16} /> : <Search size={16} />} Research
              </button>
            </div>
            {visibleResearchReport && (
              <div className="mt-4 rounded-lg border border-emerald-200 bg-white p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-black text-slate-950">Public Google Result</p>
                    <p className="mt-1 text-xs font-semibold text-slate-500">
                      {researchReport.configured ? "Google Search API configured" : "Google Search API missing"} · {researchReport.summary?.total || 0} names
                    </p>
                  </div>
                  <button onClick={downloadResearchCsv} className="inline-flex min-h-9 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:border-emerald-300 hover:text-emerald-700">
                    <Download size={14} /> CSV
                  </button>
                </div>
                {affiliateResearchError(visibleResearchReport) && (
                  <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold leading-5 text-red-700">
                    {affiliateResearchError(visibleResearchReport)}
                  </div>
                )}
                <div className="mt-3 space-y-2">
                  {(visibleResearchReport.items || []).map((item) => (
                    <div key={`${item.project_name}-${item.status}`} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-black text-slate-950">{item.project_name}</p>
                        <span className="rounded-full bg-white px-3 py-1 text-xs font-black uppercase text-slate-600">{item.status}</span>
                      </div>
                      <div className="mt-3 grid gap-2 text-xs font-semibold">
                        {item.official_domain && (
                          <p className="break-all text-slate-700">
                            <span className="font-black text-slate-950">Domain:</span> {item.official_domain}
                          </p>
                        )}
                        {item.official_url && (
                          <p className="break-all text-blue-700">
                            <span className="font-black text-slate-950">Website:</span> {item.official_url}
                          </p>
                        )}
                        {item.signup_url && (
                          <p className="break-all text-indigo-700">
                            <span className="font-black text-slate-950">Signup:</span> {item.signup_url}
                          </p>
                        )}
                        {item.affiliate_url && (
                          <p className="break-all text-emerald-700">
                            <span className="font-black text-slate-950">Affiliate:</span> {item.affiliate_url}
                          </p>
                        )}
                      </div>
                      {item.error && <p className="mt-2 break-all text-xs font-semibold text-red-700">{item.error}</p>}
                      {!!item.candidates?.length && (
                        <p className="mt-2 break-all text-xs font-semibold text-slate-500">
                          Top: {item.candidates.slice(0, 2).map((candidate) => candidate.url).join(" | ")}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-6 flex items-center justify-between gap-3 border-b border-slate-100 pb-5">
          <div>
            <h2 className="text-lg font-bold text-slate-950">Wrapped Link Output</h2>
            <p className="mt-1 text-sm font-semibold text-slate-500">Domain matching, duplicate protection, short link and click tracking.</p>
          </div>
          {result?.matched && (
            <span className="rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-xs font-black uppercase tracking-[0.14em] text-emerald-700">
              {result.program.network}
            </span>
          )}
        </div>
        {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">{error}</div>}
        {!result && <p className="text-sm font-semibold text-slate-500">Enter a product URL from Amazon, Shopee, Lazada, Accesstrade, CJ, Impact, or PartnerStack to generate an affiliate URL.</p>}
        {result && (
          <div className="space-y-4">
            <div className={`rounded-lg border px-4 py-3 text-sm font-bold ${result.matched ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
              {result.message}
            </div>
            {(result.short_url || "").includes("localhost") && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-bold text-amber-800">
                Localhost short links only work on this machine. Use the affiliate URL below, or enter a public tracking domain before shortening.
              </div>
            )}
            <div className="space-y-3">
              <AssetRow>{result.affiliate_url}</AssetRow>
              {result.tracking_url && result.tracking_url !== result.short_url && <AssetRow>{result.tracking_url}</AssetRow>}
              {result.short_url && <AssetRow>{result.short_url}</AssetRow>}
            </div>
            <div className="grid gap-3 text-sm font-semibold text-slate-600 md:grid-cols-2">
              <p>Matched: <span className="text-slate-950">{result.matched ? "Yes" : "No"}</span></p>
              <p>Already wrapped: <span className="text-slate-950">{result.already_wrapped ? "Yes" : "No"}</span></p>
              <p>Program: <span className="text-slate-950">{result.program?.name || "None"}</span></p>
              <p>Short code: <span className="text-slate-950">{result.short_code || "None"}</span></p>
            </div>
            <div className="flex flex-wrap gap-3">
              <button onClick={() => {
                const trackedLink = result.short_url || result.tracking_url;
                copy((trackedLink || "").includes("localhost") ? result.affiliate_url : (trackedLink || result.affiliate_url));
              }} className={primaryButton}>
                <Clipboard size={16} /> Copy Final Link
              </button>
              {result.short_code && (
                <button onClick={loadStats} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 hover:border-blue-300 hover:text-blue-700">
                  <MousePointerClick size={16} /> Refresh Click Stats
                </button>
              )}
            </div>
            {stats && (
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm font-semibold text-blue-900">
                Clicks: {stats.clicks} · Last click: {stats.last_clicked_at || "none"}
              </div>
            )}
          </div>
        )}
      </div>

      {projectNameResult && (
        <div className="lg:col-span-2 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
            <div>
              <h2 className="text-lg font-bold text-slate-950">Local Project Match</h2>
              <p className="mt-1 text-sm font-semibold text-slate-500">
                Query "{projectNameResult.query}" found {projectNameResult.items?.length || 0} local project rows; configured affiliate matches {projectNameResult.matched_count}; needs public lookup {projectNameResult.unmatched_count}.
              </p>
            </div>
            <span className="rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-xs font-black uppercase text-emerald-700">
              {projectNameResult.items?.length || 0} rows
            </span>
          </div>
          {!projectNameResult.items?.length && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-800">
              No affiliate project found by that name.
              {projectNameResult.suggestions?.length ? ` Try: ${projectNameResult.suggestions.join(", ")}.` : ""}
            </div>
          )}
          <div className="grid gap-3 md:grid-cols-2">
            {(projectNameResult.items || []).map((project) => (
              <div key={`${project.url}-${project.program?.name || "none"}-name-filter`} className={`rounded-lg border p-4 ${project.matched ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-slate-50"}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-black text-slate-950">{project.name}</p>
                    <p className="mt-1 break-all text-xs font-semibold text-slate-500">{project.domain || project.url}</p>
                  </div>
                  <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-black uppercase ${project.matched ? "bg-white text-emerald-700" : "bg-white text-slate-500"}`}>
                    {project.matched ? project.program.network : "No match"}
                  </span>
                </div>
                <div className={`mt-3 rounded-lg border px-3 py-2 text-sm font-black ${project.has_affiliate ? "border-emerald-200 bg-white text-emerald-800" : "border-amber-200 bg-white text-amber-800"}`}>
                  {project.has_affiliate ? "Affiliate configured" : "Not in local affiliate config. Use Public Google scan to research it."}
                </div>
                {project.program && (
                  <div className="mt-3 text-sm font-bold text-emerald-800">
                    <p>{project.program.name}</p>
                    <p className="mt-1 break-all text-xs text-emerald-700">Link dang ky: {project.signup_url || project.program.signup_url || "Not configured"}</p>
                    <p className="mt-1 break-all text-xs text-emerald-700">Params: {Object.keys(project.program.affiliate_params || {}).join(", ") || "none"}</p>
                  </div>
                )}
                <div className="mt-4 flex flex-wrap gap-2">
                  {(project.signup_url || project.program?.signup_url) && (
                    <a
                      href={project.signup_url || project.program.signup_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-700"
                    >
                      <Link size={14} /> Open Signup
                    </a>
                  )}
                  <button
                    onClick={() => useProject(project)}
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-slate-950 px-3 py-2 text-xs font-bold text-white hover:bg-blue-700"
                  >
                    <Link size={14} /> Use URL
                  </button>
                  <button
                    onClick={() => copy(project.signup_url || project.program?.signup_url || project.url)}
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:border-blue-300 hover:text-blue-700"
                  >
                    <Clipboard size={14} /> Copy Signup
                  </button>
                  {!project.has_affiliate && (
                    <button
                      onClick={scanPublicGoogleProject}
                      disabled={researchLoading}
                      className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-800 hover:border-emerald-400 disabled:opacity-60"
                    >
                      {researchLoading ? <Loader2 className="animate-spin" size={14} /> : <Search size={14} />} Scan Public Google
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {projectScan && (
        <div className="lg:col-span-2 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
            <div>
              <h2 className="text-lg font-bold text-slate-950">Affiliate-Ready Projects</h2>
              <p className="mt-1 text-sm font-semibold text-slate-500">
                Matched {projectScan.matched_count} projects from {projectScan.source}; unmatched {projectScan.unmatched_count}.
                {projectScan.source === "google_ads_live" && ` Google Ads rows ${projectScan.google_ads_project_count}/${projectScan.google_ads_total_before_filter}${projectScan.project_name ? ` for "${projectScan.project_name}"` : ""}.`}
              </p>
            </div>
            <span className="rounded-full border border-blue-200 bg-blue-50 px-4 py-2 text-xs font-black uppercase text-blue-700">
              {projectScan.items?.length || 0} rows
            </span>
          </div>
          {!projectScan.items?.length && <p className="text-sm font-semibold text-slate-500">No affiliate programs matched the available project URLs.</p>}
          <div className="grid gap-3 md:grid-cols-2">
            {(projectScan.items || []).map((project) => (
              <div key={`${project.url}-${project.program?.name || "none"}`} className={`rounded-lg border p-4 ${project.matched ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-slate-50"}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-black text-slate-950">{project.name}</p>
                    <p className="mt-1 break-all text-xs font-semibold text-slate-500">{project.url}</p>
                  </div>
                  <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-black uppercase ${project.matched ? "bg-white text-emerald-700" : "bg-white text-slate-500"}`}>
                    {project.matched ? project.program.network : "No match"}
                  </span>
                </div>
                {project.program && (
                  <div className="mt-3 text-sm font-bold text-emerald-800">
                    <p>{project.program.name}</p>
                    <p className="mt-1 break-all text-xs text-emerald-700">Link dang ky: {project.program.signup_url || "Not configured"}</p>
                  </div>
                )}
                <div className="mt-4 flex flex-wrap gap-2">
                  {project.program?.signup_url && (
                    <a
                      href={project.program.signup_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-700"
                    >
                      <Link size={14} /> Open Signup
                    </a>
                  )}
                  <button
                    onClick={() => useProject(project)}
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-slate-950 px-3 py-2 text-xs font-bold text-white hover:bg-blue-700"
                  >
                    <Link size={14} /> Use URL
                  </button>
                  <button
                    onClick={() => copy(project.url)}
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:border-blue-300 hover:text-blue-700"
                  >
                    <Clipboard size={14} /> Copy URL
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function PublishHistory({ primaryButton }) {
  const [items, setItems] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const csvUrl = `${apiBase}/google-ads/publish-history/export.csv`;

  const loadHistory = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/google-ads/publish-history?limit=100`);
      if (!response.ok) throw new Error("Cannot load publish history");
      const data = await response.json();
      setItems(data.items || []);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  React.useEffect(() => {
    loadHistory();
  }, []);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-5">
        <div className="flex items-center gap-2">
          <History className="text-blue-600" size={18} />
          <div>
            <h2 className="text-lg font-bold text-slate-950">Publish History</h2>
            <p className="mt-1 text-sm font-semibold text-slate-500">Content used by account ID, campaign setup, and measurement fields.</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={loadHistory} disabled={loading} className={primaryButton}>
            {loading ? <Loader2 className="animate-spin" size={16} /> : <History size={16} />} Refresh
          </button>
          <button onClick={() => navigator.clipboard?.writeText(csvUrl)} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 hover:border-blue-300 hover:text-blue-700">
            <Clipboard size={16} /> Copy CSV Link
          </button>
          <a href={csvUrl} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-blue-700">
            <Link size={16} /> Open CSV
          </a>
        </div>
      </div>

      <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-900">
        Google Sheets: open a new Sheet, choose Import, then paste or upload this CSV export. The CSV link contains campaign, customer IDs, content, schedule and metrics fields.
      </div>

      {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">{error}</div>}
      {!items.length && <p className="text-sm font-semibold text-slate-500">No publish history yet. Validate or publish a campaign to store the content and selected account IDs.</p>}

      <div className="space-y-4">
        {items.map((item) => (
          <article key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-black text-slate-950">{item.campaign_name}</h3>
                <p className="mt-1 text-xs font-bold uppercase text-slate-500">{new Date(item.created_at).toLocaleString("vi-VN")}</p>
              </div>
              <span className={`rounded-full border px-3 py-1 text-xs font-black uppercase tracking-[0.12em] ${item.status === "published" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-blue-200 bg-blue-50 text-blue-700"}`}>
                {item.mode}
              </span>
            </div>

            <div className="mt-4 grid gap-4 text-sm font-semibold text-slate-600 lg:grid-cols-3">
              <div className="rounded-lg bg-white p-4">
                <p className="text-xs font-black uppercase text-slate-500">Accounts</p>
                <p className="mt-2 text-slate-950">{(item.customer_ids || []).join(", ") || "None"}</p>
                <p className="mt-2 break-all text-slate-500">{item.landing_page_url}</p>
              </div>
              <div className="rounded-lg bg-white p-4">
                <p className="text-xs font-black uppercase text-slate-500">Budget</p>
                <p className="mt-2 text-slate-950">{formatMoney(item.budget?.daily_budget_vnd, item.budget?.currency_code)}</p>
                <p className="mt-1 text-slate-500">CPC {formatMoney(item.budget?.manual_cpc_bid_vnd, item.budget?.currency_code)}</p>
              </div>
              <div className="rounded-lg bg-white p-4">
                <p className="text-xs font-black uppercase text-slate-500">Metrics</p>
                <p className="mt-2 text-slate-950">Clicks {formatNumber(item.metrics?.clicks)} · Conv {formatNumber(item.metrics?.conversions)}</p>
                <p className="mt-1 text-slate-500">Cost {formatMoney(item.metrics?.cost, item.budget?.currency_code)}</p>
              </div>
            </div>

            {item.schedule?.enabled && (
              <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm font-semibold text-blue-900">
                Scheduled for {new Date(item.schedule.scheduled_at).toLocaleString("vi-VN")} ({item.schedule.timezone || "Asia/Saigon"})
              </div>
            )}

            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <div className="rounded-lg bg-white p-4">
                <p className="mb-3 text-xs font-black uppercase text-slate-500">Headlines Used</p>
                <div className="flex flex-wrap gap-2">
                  {(item.content?.headlines || []).map((headline, index) => (
                    <span key={`${item.id}-headline-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-bold text-slate-700">{headline}</span>
                  ))}
                </div>
              </div>
              <div className="rounded-lg bg-white p-4">
                <p className="mb-3 text-xs font-black uppercase text-slate-500">Descriptions Used</p>
                <div className="space-y-2">
                  {(item.content?.descriptions || []).map((description, index) => (
                    <p key={`${item.id}-description-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-bold text-slate-700">{description}</p>
                  ))}
                </div>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function DailyAutomation({ accountStatus, inputClass, textareaClass, primaryButton }) {
  const accounts = accountStatus.accounts || [];
  const [form, setForm] = React.useState({
    workflow_name: "Daily Search Ads Automation",
    product_name: "",
    landing_page_url: "",
    target_keywords: "",
    target_audience: "",
    primary_offer: "",
    primary_cta: "",
    daily_budget_vnd: 300000,
    manual_cpc_bid_vnd: 5000,
    currency_code: "VND",
    target_location: "Vietnam",
    excluded_locations: "",
    customer_ids: [],
    dry_run: true,
    schedule_enabled: false,
    scheduled_at: "",
  });
  const [result, setResult] = React.useState(null);
  const [schedulerResult, setSchedulerResult] = React.useState(null);
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [schedulerLoading, setSchedulerLoading] = React.useState(false);

  React.useEffect(() => {
    const firstPublishable = accounts.find((account) => account.publish_eligible !== false);
    if (!form.customer_ids.length && firstPublishable) {
      setForm((current) => ({ ...current, customer_ids: [firstPublishable.customer_id] }));
    }
  }, [accounts.length]);

  const toggleCustomerId = (customerId) => {
    setForm((current) => ({
      ...current,
      customer_ids: current.customer_ids.includes(customerId)
        ? current.customer_ids.filter((item) => item !== customerId)
        : [...current.customer_ids, customerId],
    }));
  };

  const runAutomation = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const payload = {
        ...form,
        target_keywords: toLines(form.target_keywords),
        excluded_locations: toLines(form.excluded_locations),
        daily_budget_vnd: Number(form.daily_budget_vnd),
        manual_cpc_bid_vnd: Number(form.manual_cpc_bid_vnd),
        currency_code: form.currency_code,
        scheduled_at: form.schedule_enabled ? toIsoDateTime(form.scheduled_at) : null,
        schedule_timezone: "Asia/Saigon",
      };
      setResult(await postApi("/automation/daily-run", payload));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  const previewScheduler = async () => {
    setSchedulerLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/google-ads/scheduled/run-due?dry_run=true&limit=10`, { method: "POST" });
      if (!response.ok) throw new Error("Cannot preview scheduled jobs");
      setSchedulerResult(await response.json());
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSchedulerLoading(false);
    }
  };

  return (
    <section className="grid gap-6 lg:grid-cols-[430px_1fr]">
      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-5 flex items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div className="flex items-center gap-2">
            <Zap className="text-blue-600" size={18} />
            <h2 className="text-sm font-black uppercase text-slate-950">Daily Automation Demo</h2>
          </div>
          <span className="rounded-md bg-blue-50 px-2.5 py-1 text-xs font-bold text-blue-700">Test workflow</span>
        </div>
        <div className="grid gap-4">
          <Field label="Workflow Name">
            <input className={inputClass} value={form.workflow_name} onChange={(event) => setForm({ ...form, workflow_name: event.target.value })} />
          </Field>
          <Field label="Landing Page URL">
            <input className={inputClass} value={form.landing_page_url} onChange={(event) => {
              setForm({ ...form, landing_page_url: event.target.value });
              setResult(null);
            }} />
          </Field>
          <Field label="Product Name">
            <input className={inputClass} value={form.product_name} onChange={(event) => setForm({ ...form, product_name: event.target.value })} />
          </Field>
          <Field label="Keywords">
            <textarea className={textareaClass} value={form.target_keywords} onChange={(event) => setForm({ ...form, target_keywords: event.target.value })} />
          </Field>
          <div className="grid gap-3 md:grid-cols-3">
            <Field label="Currency">
              <select
                className={inputClass}
                value={form.currency_code}
                onChange={(event) => setForm({
                  ...form,
                  currency_code: event.target.value,
                  daily_budget_vnd: event.target.value === "USD" ? 15 : 300000,
                  manual_cpc_bid_vnd: event.target.value === "USD" ? 0.25 : 5000,
                })}
              >
                <option value="VND">VND (₫)</option>
                <option value="USD">USD ($)</option>
              </select>
            </Field>
            <Field label={`Budget ${form.currency_code}`}>
              <input className={inputClass} type="number" min={form.currency_code === "USD" ? "2" : "50000"} step={form.currency_code === "USD" ? "0.01" : "1000"} value={form.daily_budget_vnd} onChange={(event) => setForm({ ...form, daily_budget_vnd: event.target.value })} />
            </Field>
            <Field label={`Manual CPC ${form.currency_code}`}>
              <input className={inputClass} type="number" min={form.currency_code === "USD" ? "0.05" : "1000"} step={form.currency_code === "USD" ? "0.01" : "100"} value={form.manual_cpc_bid_vnd} onChange={(event) => setForm({ ...form, manual_cpc_bid_vnd: event.target.value })} />
            </Field>
          </div>
          <label className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-bold text-slate-700">
            <input type="checkbox" checked={form.dry_run} onChange={(event) => setForm({ ...form, dry_run: event.target.checked })} />
            Demo dry-run first
          </label>
          <label className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-bold text-slate-700">
            <input type="checkbox" checked={form.schedule_enabled} onChange={(event) => setForm({ ...form, schedule_enabled: event.target.checked })} />
            Save as scheduled daily run
          </label>
          {form.schedule_enabled && (
            <Field label="Scheduled Time">
              <input className={inputClass} type="datetime-local" value={form.scheduled_at} onChange={(event) => setForm({ ...form, scheduled_at: event.target.value })} />
            </Field>
          )}
          <button onClick={runAutomation} disabled={loading || !form.customer_ids.length || !form.landing_page_url.trim() || !form.product_name.trim()} className={primaryButton}>
            {loading ? <Loader2 className="animate-spin" size={16} /> : <Zap size={16} />} Run Daily Workflow Demo
          </button>
        </div>
      </div>

      <div className="space-y-6">
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <p className="mb-3 text-xs font-black uppercase text-slate-500">Test Accounts</p>
          <div className="grid gap-2 md:grid-cols-2">
            {accounts.map((account) => (
              <label key={account.customer_id} title={account.status_description || ""} className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm font-bold transition ${account.publish_eligible === false ? "cursor-not-allowed border-slate-200 bg-slate-100 opacity-75" : form.customer_ids.includes(account.customer_id) ? "border-blue-300 bg-blue-50 text-blue-900" : "border-slate-200 bg-white text-slate-700"}`}>
                <input className="mt-1" disabled={account.publish_eligible === false} type="checkbox" checked={form.customer_ids.includes(account.customer_id)} onChange={() => toggleCustomerId(account.customer_id)} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-start justify-between gap-2"><span className="block truncate text-slate-950">{account.label}</span><AccountStatusBadge account={account} /></span>
                  <span className="mt-1 block text-xs text-slate-400">Customer ID {account.customer_id}</span>
                </span>
              </label>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <p className="mb-3 text-xs font-black uppercase text-slate-500">Workflow Steps</p>
          <div className="grid gap-3 md:grid-cols-5">
            {["Read page", "Write RSA", "Select keywords", "Validate/publish", "Store history"].map((step) => (
              <div key={step} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm font-bold text-slate-700">{step}</div>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button onClick={previewScheduler} disabled={schedulerLoading} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 hover:border-blue-300 hover:text-blue-700 disabled:opacity-50">
              {schedulerLoading ? <Loader2 className="animate-spin" size={16} /> : <History size={16} />} Preview Due Scheduler
            </button>
            {schedulerResult && (
              <span className="text-sm font-bold text-slate-600">
                Due: {schedulerResult.due} · Previewed: {schedulerResult.results?.length || 0}
              </span>
            )}
          </div>
        </div>

        {error && <div className="whitespace-pre-line rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">{error}</div>}
        {result && (
          <div className="rounded-lg border border-emerald-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-black text-emerald-900">{result.publish_result?.message}</p>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <div className="rounded-lg bg-slate-50 p-4">
                <p className="text-xs font-black uppercase text-slate-500">Mode</p>
                <p className="mt-1 text-sm font-bold text-slate-950">{result.publish_result?.mode}</p>
              </div>
              <div className="rounded-lg bg-slate-50 p-4">
                <p className="text-xs font-black uppercase text-slate-500">Accounts</p>
                <p className="mt-1 text-sm font-bold text-slate-950">{(result.publish_result?.customer_ids || []).join(", ")}</p>
              </div>
            </div>
            <div className="mt-4">
              <p className="mb-2 text-xs font-black uppercase text-slate-500">Generated Headlines</p>
              <div className="flex flex-wrap gap-2">
                {(result.generated_ads?.headlines || []).slice(0, 8).map((headline) => (
                  <span key={headline} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-bold text-slate-700">{headline}</span>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function CampaignCsvImport({ accounts, onApply, canPublishLive }) {
  const [fileName, setFileName] = React.useState("");
  const [rows, setRows] = React.useState([]);
  const [selectedIndex, setSelectedIndex] = React.useState(0);
  const [message, setMessage] = React.useState("");
  const [batchRunning, setBatchRunning] = React.useState(false);
  const [batchProgress, setBatchProgress] = React.useState({ completed: 0, total: 0 });
  const [batchResults, setBatchResults] = React.useState([]);

  const loadFile = async (file) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setRows([]);
      setMessage("Vui lòng chọn file .csv");
      return;
    }
    const parsedRows = campaignRowsFromCsv(await file.text());
    setFileName(file.name);
    setRows(parsedRows);
    setBatchResults([]);
    setBatchProgress({ completed: 0, total: parsedRows.length });
    setSelectedIndex(Math.max(0, parsedRows.findIndex((row) => !row.errors.length)));
    setMessage(parsedRows.length
      ? `Đã đọc ${parsedRows.length} dòng. Chọn một dòng để nạp vào workflow.`
      : "Không đọc được dữ liệu. CSV cần có header landing_page_url và ít nhất một dòng dữ liệu.");
  };

  const downloadTemplate = () => {
    const sampleAccount = (accounts || []).find((account) => account.publish_eligible !== false);
    const sampleCustomerId = sampleAccount?.customer_id || "1234567890";
    const sampleCurrency = sampleAccount?.currency_code || "VND";
    const sampleBudget = sampleCurrency === "USD" ? 15 : 300000;
    const sampleCpc = sampleCurrency === "USD" ? 0.25 : 5000;
    const content = [
      "landing_page_url,product_name,campaign_name,ad_group_name,keywords,language,tone,target_audience,primary_offer,primary_cta,trust_signals,daily_budget,cpc,currency,target_location,excluded_locations,excluded_location_ids,customer_ids,schedule_enabled,scheduled_at,schedule_timezone",
      `https://example.com,Example,Search - Example,Example - Exact,"buy example|example pricing",Vietnamese,Professional,Khach hang Viet Nam,Giam 20%,Mua Ngay,Ho tro chuyen nghiep,${sampleBudget},${sampleCpc},${sampleCurrency},Vietnam,"United States|India","2840|2356",${sampleCustomerId},false,,Asia/Saigon`,
    ].join("\n");
    const anchor = document.createElement("a");
    anchor.href = URL.createObjectURL(new Blob([`\uFEFF${content}`], { type: "text/csv;charset=utf-8" }));
    anchor.download = "google-ads-campaign-template.csv";
    anchor.click();
    URL.revokeObjectURL(anchor.href);
  };

  const selectedRow = rows[selectedIndex];
  const accountsById = new Map((accounts || []).map((account) => [account.customer_id, account]));
  const knownIds = new Set(accountsById.keys());
  const unknownIds = (selectedRow?.customer_ids || []).filter((customerId) => !knownIds.has(customerId));
  const issuesForRow = (row) => {
    const issues = [...(row.errors || [])];
    if (!row.currency_code) issues.push("Thiếu currency");
    if (!row.customer_ids.length) issues.push("Thiếu customer_ids");
    row.customer_ids.forEach((customerId) => {
      const account = accountsById.get(customerId);
      if (!account) issues.push(`Account ${customerId} không thuộc MCC`);
      else if (account.publish_eligible === false) issues.push(`Account ${customerId} không Active`);
      else if (row.currency_code && account.currency_code && row.currency_code !== account.currency_code) {
        issues.push(`Account ${customerId} dùng ${account.currency_code}, không phải ${row.currency_code}`);
      }
    });
    if (row.schedule_enabled && !row.scheduled_at) issues.push("Thiếu scheduled_at");
    if (row.schedule_enabled && row.scheduled_at && Number.isNaN(new Date(row.scheduled_at).getTime())) issues.push("scheduled_at không hợp lệ");
    return [...new Set(issues)];
  };
  const runnableRows = rows.filter((row) => !issuesForRow(row).length);
  const selectedIssues = selectedRow ? issuesForRow(selectedRow) : [];

  const runBatch = async (publishLive) => {
    if (!runnableRows.length || batchRunning) return;
    if (publishLive && !canPublishLive) {
      setMessage("Chưa đủ quyền publish live. Hãy kết nối Google Ads và bật live mutations trước.");
      return;
    }
    if (publishLive) {
      const totalDailyBudget = runnableRows.reduce((total, row) => total + Number(row.daily_budget_vnd || (row.currency_code === "USD" ? 15 : 300000)), 0);
      const confirmed = window.confirm(
        `Publish ${runnableRows.length} campaign từ CSV?\n\nTổng ngân sách khai báo: ${formatNumber(totalDailyBudget)} (có thể gồm nhiều loại tiền).\n\nCampaign có thể bắt đầu chi tiêu sau khi Google phê duyệt.`,
      );
      if (!confirmed) return;
    }

    setBatchRunning(true);
    setBatchResults([]);
    setBatchProgress({ completed: 0, total: rows.length });
    const results = [];
    for (const row of rows) {
      const issues = issuesForRow(row);
      if (issues.length) {
        results.push({ rowNumber: row.rowNumber, campaignName: row.campaign_name || row.product_name, status: "skipped", message: issues.join(" · ") });
      } else {
        try {
          const generated = normalizeAssets(await postApi("/ai/generate-ads", {
            product_name: row.product_name,
            website: row.landing_page_url,
            landing_page_url: row.landing_page_url,
            language: row.language || "English",
            tone: row.tone || "Professional",
            target_audience: row.target_audience,
            primary_offer: row.primary_offer,
            primary_cta: row.primary_cta,
            trust_signals: row.trust_signals,
            target_keywords: toLines(row.target_keywords || ""),
          }));
          const keywords = toLines(row.target_keywords || "").length
            ? toLines(row.target_keywords)
            : (generated.landing_page_alignment?.keywords_used || []);
          if (generated.headlines.length < 3 || generated.descriptions.length < 2 || !keywords.length) {
            throw new Error("Không tạo đủ RSA assets hoặc keywords hợp lệ.");
          }
          const publishResult = await postApi("/google-ads/campaigns/publish", {
            campaign_name: row.campaign_name || `Search - ${row.product_name || `Row ${row.rowNumber}`}`,
            ad_group_name: row.ad_group_name || `${row.product_name || `Row ${row.rowNumber}`} - Exact`,
            daily_budget_vnd: Number(row.daily_budget_vnd || (row.currency_code === "USD" ? 15 : 300000)),
            manual_cpc_bid_vnd: Number(row.manual_cpc_bid_vnd || (row.currency_code === "USD" ? 0.25 : 5000)),
            currency_code: row.currency_code || "VND",
            landing_page_url: row.landing_page_url,
            target_location: row.target_location || "Vietnam",
            excluded_locations: toLines(row.excluded_locations || ""),
            excluded_location_ids: toLines(row.excluded_location_ids || "").map(Number).filter(Boolean),
            keywords,
            headlines: generated.headlines,
            descriptions: generated.descriptions,
            customer_ids: row.customer_ids,
            schedule_enabled: publishLive && row.schedule_enabled,
            scheduled_at: publishLive && row.schedule_enabled ? toIsoDateTime(row.scheduled_at) : null,
            schedule_timezone: row.schedule_timezone || "Asia/Saigon",
            enable_immediately: publishLive && !row.schedule_enabled,
            dry_run: !publishLive,
          });
          results.push({
            rowNumber: row.rowNumber,
            campaignName: row.campaign_name || row.product_name,
            status: publishResult.mode === "dry_run" ? "validated" : publishResult.mode,
            message: publishResult.message,
            customerIds: publishResult.customer_ids || [],
          });
        } catch (error) {
          results.push({ rowNumber: row.rowNumber, campaignName: row.campaign_name || row.product_name, status: "error", message: error.message });
        }
      }
      setBatchResults([...results]);
      setBatchProgress({ completed: results.length, total: rows.length });
    }
    const successful = results.filter((item) => ["validated", "live", "scheduled"].includes(item.status)).length;
    setMessage(`Hoàn tất ${results.length} dòng: ${successful} thành công, ${results.length - successful} lỗi/bỏ qua.`);
    setBatchRunning(false);
  };

  return (
    <section className="surface-card overflow-hidden p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-blue-100 text-blue-700"><Upload size={18} /></div>
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.14em] text-blue-700">Bước 0 · Nhập dữ liệu</p>
            <h2 className="mt-1 text-base font-black text-slate-950">Upload CSV chiến dịch Google Ads</h2>
            <p className="mt-1 text-xs font-semibold leading-5 text-slate-500">Nạp tối đa 50 landing page, ngân sách, keyword và customer ID để tạo campaign hàng loạt.</p>
          </div>
        </div>
        <button type="button" onClick={downloadTemplate} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:border-blue-300 hover:text-blue-700">
          <Download size={15} /> Tải file mẫu
        </button>
      </div>
      <label
        className="mt-4 flex min-h-24 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-blue-200 bg-blue-50/60 px-4 py-5 text-center transition hover:border-blue-400 hover:bg-blue-50"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          loadFile(event.dataTransfer.files?.[0]);
        }}
      >
        <Upload className="text-blue-600" size={20} />
        <span className="mt-2 text-sm font-black text-blue-950">{fileName || "Chọn hoặc kéo thả file CSV"}</span>
        <span className="mt-1 text-xs font-semibold text-blue-700">File được xử lý ngay trên trình duyệt, chưa publish lên Google Ads.</span>
        <input type="file" accept=".csv,text/csv" className="hidden" onChange={(event) => loadFile(event.target.files?.[0])} />
      </label>
      {message && <p className={`mt-3 text-xs font-bold ${rows.length ? "text-emerald-700" : "text-amber-700"}`}>{message}</p>}
      {rows.length > 0 && (
        <>
        <div className="mt-4 grid gap-3 lg:grid-cols-[220px_1fr_auto] lg:items-end">
          <Field label="Dòng CSV">
            <select className="form-input" value={selectedIndex} onChange={(event) => setSelectedIndex(Number(event.target.value))}>
              {rows.map((row, index) => (
                <option key={row.rowNumber} value={index}>Dòng {row.rowNumber} · {row.product_name || row.campaign_name || row.landing_page_url || "Không hợp lệ"}</option>
              ))}
            </select>
          </Field>
          <div className={`rounded-lg border px-4 py-3 text-xs font-semibold ${selectedIssues.length ? "border-amber-200 bg-amber-50 text-amber-900" : "border-emerald-200 bg-emerald-50 text-emerald-900"}`}>
            <p className="font-black">{selectedRow?.landing_page_url || "Chưa có landing page"}</p>
            <p className="mt-1">{selectedRow?.target_keywords ? `${selectedRow.target_keywords.split("\n").length} keywords` : "Keyword sẽ được AI trích xuất"} · {(selectedRow?.customer_ids || []).length || "Không có"} customer IDs</p>
            {selectedRow?.errors.map((item) => <p key={item} className="mt-1">• {item}</p>)}
            {unknownIds.length > 0 && <p className="mt-1">• Customer ID chưa có trong MCC: {unknownIds.join(", ")}</p>}
            {selectedIssues
              .filter((item) => !(selectedRow?.errors || []).includes(item) && !item.includes("không thuộc MCC"))
              .map((item) => <p key={item} className="mt-1">• {item}</p>)}
          </div>
          <button type="button" disabled={!selectedRow || selectedIssues.length > 0} onClick={() => onApply(selectedRow)} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
            <CheckCircle2 size={16} /> Áp dụng dòng này
          </button>
        </div>
        <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-black uppercase tracking-wide text-slate-700">Batch campaign runner</p>
              <p className="mt-1 text-xs font-semibold text-slate-500">
                {runnableRows.length}/{rows.length} dòng hợp lệ · xử lý tuần tự để theo dõi lỗi từng campaign
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button type="button" disabled={batchRunning || !runnableRows.length} onClick={() => runBatch(false)} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-blue-200 bg-white px-3 py-2 text-xs font-black text-blue-700 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50">
                {batchRunning ? <Loader2 className="animate-spin" size={15} /> : <ShieldCheck size={15} />} Validate All Drafts
              </button>
              <button type="button" disabled={batchRunning || !runnableRows.length || !canPublishLive} onClick={() => runBatch(true)} className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-black text-white shadow-sm hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50" title={canPublishLive ? "Publish or schedule every valid CSV row" : "Live publishing is not ready"}>
                <Rocket size={15} /> Publish Valid Rows
              </button>
            </div>
          </div>
          {batchRunning && (
            <div className="mt-4">
              <div className="mb-1 flex justify-between text-xs font-bold text-slate-600"><span>Đang xử lý</span><span>{batchProgress.completed}/{batchProgress.total}</span></div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full bg-blue-600 transition-all" style={{ width: `${batchProgress.total ? (batchProgress.completed / batchProgress.total) * 100 : 0}%` }} /></div>
            </div>
          )}
          {batchResults.length > 0 && (
            <div className="mt-4 max-h-72 space-y-2 overflow-y-auto pr-1">
              {batchResults.map((result) => {
                const successful = ["validated", "live", "scheduled"].includes(result.status);
                return (
                  <div key={`${result.rowNumber}-${result.campaignName}`} className={`rounded-lg border px-3 py-2 text-xs ${successful ? "border-emerald-200 bg-emerald-50 text-emerald-900" : result.status === "skipped" ? "border-amber-200 bg-amber-50 text-amber-900" : "border-red-200 bg-red-50 text-red-900"}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2"><strong>Dòng {result.rowNumber} · {result.campaignName || "Campaign"}</strong><span className="font-black uppercase">{result.status}</span></div>
                    <p className="mt-1 font-semibold leading-5">{result.message}</p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
        </>
      )}
    </section>
  );
}

function App() {
  const accountStatus = useApi("/google-ads/account/status", {
    google_oauth_logged_in: false,
    google_user: null,
    google_ads_scope_granted: false,
    refresh_token_available: false,
    developer_token_configured: false,
    can_publish_live: false,
    customer_id: "",
    login_customer_id: "",
    customer_ids: [],
    accounts: [],
  }, 3000);
  const [activeFlow, setActiveFlow] = React.useState("content");
  const [contentForm, setContentForm] = React.useState({
    landing_page_url: "",
    product_name: "",
    offer_identity: "",
    target_keywords: "",
    language: "English",
    tone: "Professional",
    target_audience: "",
    primary_offer: "",
    primary_cta: "",
    trust_signals: "",
  });
  const [campaignForm, setCampaignForm] = React.useState({
    campaign_name: "Search Campaign",
    ad_group_name: "Search Campaign - Core",
    daily_budget_vnd: 300000,
    manual_cpc_bid_vnd: 5000,
    currency_code: "VND",
    target_location: "Vietnam",
    excluded_locations: "",
    excluded_location_ids: "",
    schedule_enabled: false,
    scheduled_at: "",
    schedule_timezone: "Asia/Saigon",
    enable_immediately: true,
    dry_run: true,
  });
  const [generated, setGenerated] = React.useState(null);
  const [selectedCustomerIds, setSelectedCustomerIds] = React.useState([]);
  const [publishResult, setPublishResult] = React.useState(null);
  const [error, setError] = React.useState("");
  const [contentNotice, setContentNotice] = React.useState("");
  const [accountSyncNotice, setAccountSyncNotice] = React.useState("");
  const [loading, setLoading] = React.useState("");
  const previousAccountIds = React.useRef(null);
  const previousAccountStatuses = React.useRef(null);

  const selectContentProject = (project) => {
    const projectName = (project?.name || "").trim();
    setContentForm((current) => ({
      ...current,
      landing_page_url: project?.url || "",
      product_name: projectName,
      offer_identity: "",
      target_keywords: "",
      target_audience: "",
      primary_offer: "",
      primary_cta: "",
      trust_signals: "",
    }));
    setCampaignForm((current) => ({
      ...current,
      campaign_name: projectName ? `Search - ${projectName}` : "Search Campaign",
      ad_group_name: projectName ? `${projectName} - Core` : "Search Campaign - Core",
    }));
    setGenerated(null);
    setPublishResult(null);
    setContentNotice("");
    setError("");
    setActiveFlow("content");
  };

  const updateLandingPageUrl = (landingPageUrl) => {
    setContentForm((current) => ({ ...current, landing_page_url: landingPageUrl }));
    setGenerated(null);
    setPublishResult(null);
    setContentNotice("");
  };

  const updateContentField = (field, value) => {
    setContentForm((current) => ({ ...current, [field]: value }));
    setGenerated(null);
    setPublishResult(null);
    setContentNotice("");
  };

  const applyCampaignCsvRow = (row) => {
    const contentFields = [
      "landing_page_url", "product_name", "target_keywords", "language", "tone",
      "target_audience", "primary_offer", "primary_cta", "trust_signals",
    ];
    const campaignFields = [
      "campaign_name", "ad_group_name", "daily_budget_vnd", "manual_cpc_bid_vnd", "currency_code",
      "target_location", "excluded_locations", "excluded_location_ids",
    ];
    setContentForm((current) => ({
      ...current,
      ...Object.fromEntries(contentFields.filter((field) => row[field]).map((field) => [field, row[field]])),
    }));
    setCampaignForm((current) => ({
      ...current,
      ...Object.fromEntries(campaignFields.filter((field) => row[field]).map((field) => [field, row[field]])),
    }));
    if (row.customer_ids.length) setSelectedCustomerIds(row.customer_ids);
    setGenerated(null);
    setPublishResult(null);
    setError("");
    setContentNotice(`Đã nạp dòng ${row.rowNumber} từ CSV. Kiểm tra lại dữ liệu rồi bấm Analyze Page & Generate RSA.`);
    setActiveFlow("content");
  };

  React.useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const oauthError = params.get("oauth_error");
    if (oauthError) {
      setError(oauthError);
      params.delete("oauth_error");
      const query = params.toString();
      window.history.replaceState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
    }
  }, []);

  React.useEffect(() => {
    const accounts = accountStatus.accounts || [];
    const publishable = accounts.filter((account) => account.publish_eligible !== false);
    if (!publishable.length || selectedCustomerIds.length) return;
    const defaults = publishable.filter((account) => account.selected_by_default).map((account) => account.customer_id);
    setSelectedCustomerIds(defaults.length ? defaults : [publishable[0].customer_id]);
  }, [accountStatus.accounts, selectedCustomerIds.length]);

  React.useEffect(() => {
    const nextAccounts = accountStatus.accounts || [];
    const nextIds = nextAccounts.map((account) => account.customer_id);
    const publishableIds = nextAccounts
      .filter((account) => account.publish_eligible !== false)
      .map((account) => account.customer_id);
    if (!nextIds.length) return;
    const previousIds = previousAccountIds.current;
    const nextStatuses = Object.fromEntries(nextAccounts.map((account) => [account.customer_id, account.status || "NOT_SYNCED"]));
    const previousStatuses = previousAccountStatuses.current;
    if (previousIds) {
      const added = nextIds.filter((customerId) => !previousIds.includes(customerId));
      const removed = previousIds.filter((customerId) => !nextIds.includes(customerId));
      if (added.length) {
        setAccountSyncNotice(`MCC vừa cập nhật ${added.length} tài khoản mới: ${added.join(", ")}. Hãy chọn tài khoản trước khi publish.`);
      } else if (removed.length) {
        setAccountSyncNotice(`MCC đã gỡ ${removed.length} tài khoản: ${removed.join(", ")}. Danh sách publish đã được cập nhật.`);
      }
      if (removed.length) {
        setSelectedCustomerIds((current) => current.filter((customerId) => nextIds.includes(customerId)));
      }
      const changed = previousStatuses
        ? nextAccounts.filter((account) => previousStatuses[account.customer_id] && previousStatuses[account.customer_id] !== nextStatuses[account.customer_id])
        : [];
      if (changed.length) {
        setAccountSyncNotice(changed.map((account) => `${account.label}: ${account.status_label || account.status}`).join(" · "));
      }
    }
    setSelectedCustomerIds((current) => {
      const next = current.filter((customerId) => publishableIds.includes(customerId));
      return next.length === current.length ? current : next;
    });
    previousAccountIds.current = nextIds;
    previousAccountStatuses.current = nextStatuses;
  }, [accountStatus.accounts]);

  const generateContent = async () => {
    setLoading("generate");
    setError("");
    setContentNotice("");
    setPublishResult(null);
    try {
      const data = await postApi("/ai/generate-ads", {
        product_name: contentForm.product_name,
        website: contentForm.landing_page_url,
        landing_page_url: contentForm.landing_page_url,
        language: contentForm.language,
        tone: contentForm.tone,
        target_audience: contentForm.target_audience,
        landing_page_message: contentForm.offer_identity,
        primary_offer: contentForm.primary_offer,
        primary_cta: contentForm.primary_cta,
        trust_signals: contentForm.trust_signals,
        target_keywords: toLines(contentForm.target_keywords),
      });
      setGenerated(data);
      const page = data.landing_page_alignment?.page_context || {};
      setContentNotice(page.fetched
        ? `Đã đọc “${page.title || page.final_url}” và tạo ${data.headlines?.length || 0} headlines, ${data.descriptions?.length || 0} descriptions · SEO score ${data.seo_analysis?.score ?? 0}/100.`
        : `Không đọc được landing page (${page.error || "unknown error"}). Content hiện dùng dữ liệu nhập thủ công.`);
      setActiveFlow("deploy");
      window.setTimeout(() => {
        document.getElementById("creative-assets")?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 50);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading("");
    }
  };

  const deployCampaign = async (forceLive = false, schedule = false) => {
    if (
      forceLive
      && !window.confirm(
        `Publish and ENABLE this campaign now?\n\nDaily budget: ${formatMoney(campaignForm.daily_budget_vnd, campaignForm.currency_code)}\nAccounts: ${selectedCustomerIds.length}\n\nGoogle Ads may start spending after ad approval.`,
      )
    ) {
      return;
    }
    setLoading(schedule ? "schedule" : (forceLive ? "publish" : "draft"));
    setError("");
    setPublishResult(null);
    try {
      let assets = generated;
      if (!assets) {
        assets = await postApi("/ai/generate-ads", {
          product_name: contentForm.product_name,
          website: contentForm.landing_page_url,
          landing_page_url: contentForm.landing_page_url,
          language: contentForm.language,
          tone: contentForm.tone,
          target_audience: contentForm.target_audience,
          landing_page_message: contentForm.offer_identity,
          primary_offer: contentForm.primary_offer,
          primary_cta: contentForm.primary_cta,
          trust_signals: contentForm.trust_signals,
          target_keywords: toLines(contentForm.target_keywords),
        });
        setGenerated(assets);
      }
      assets = normalizeAssets(assets);
      const invalidHeadline = assets.headlines.find((item) => item.length > 30);
      const invalidDescription = assets.descriptions.find((item) => item.length > 90);
      if (assets.headlines.length < 3) {
        throw new Error("Can it nhat 3 headline truoc khi dang.");
      }
      if (assets.descriptions.length < 2) {
        throw new Error("Can it nhat 2 description truoc khi dang.");
      }
      if (invalidHeadline) {
        throw new Error(`Headline vuot 30 ky tu: ${invalidHeadline}`);
      }
      if (invalidDescription) {
        throw new Error(`Description vuot 90 ky tu: ${invalidDescription}`);
      }
      if (!selectedCustomerIds.length) {
        throw new Error("Chon it nhat 1 tai khoan Google Ads truoc khi dang.");
      }
      if (schedule && !campaignForm.scheduled_at) {
        throw new Error("Chon thoi gian dang truoc khi luu lich.");
      }
      setGenerated(assets);
      const payload = {
        campaign_name: campaignForm.campaign_name,
        ad_group_name: campaignForm.ad_group_name,
        daily_budget_vnd: Number(campaignForm.daily_budget_vnd),
        manual_cpc_bid_vnd: Number(campaignForm.manual_cpc_bid_vnd),
        currency_code: campaignForm.currency_code,
        landing_page_url: contentForm.landing_page_url,
        target_location: campaignForm.target_location,
        excluded_locations: toLines(campaignForm.excluded_locations),
        excluded_location_ids: toLines(campaignForm.excluded_location_ids).map((item) => Number(item)).filter(Boolean),
        keywords: assets.landing_page_alignment?.keywords_used?.length ? assets.landing_page_alignment.keywords_used : toLines(contentForm.target_keywords),
        headlines: assets.headlines,
        descriptions: assets.descriptions,
        customer_ids: selectedCustomerIds,
        schedule_enabled: schedule,
        scheduled_at: schedule ? toIsoDateTime(campaignForm.scheduled_at) : null,
        schedule_timezone: campaignForm.schedule_timezone,
        enable_immediately: forceLive ? true : campaignForm.enable_immediately,
        dry_run: !forceLive && campaignForm.dry_run,
      };
      setPublishResult(await postApi("/google-ads/campaigns/publish", payload));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading("");
    }
  };

  const connectGoogleAds = () => {
    window.location.assign(`${apiBase}/auth/google/connect-ads`);
  };

  const downloadAdsCsv = () => {
    const plan = publishResult?.plan;
    if (!plan?.ad_group?.name) return;
    const anchor = document.createElement("a");
    anchor.href = URL.createObjectURL(new Blob([`\uFEFF${adsEditorCsvFromPlan(plan)}`], { type: "text/csv;charset=utf-8" }));
    anchor.download = `${safeFilePart(plan.ad_group.name)}-ads.csv`;
    anchor.click();
    URL.revokeObjectURL(anchor.href);
  };

  const inputClass = "w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100";
  const textareaClass = `${inputClass} min-h-28 resize-y`;
  const primaryButton = "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60";
  const toggleCustomerId = (customerId) => {
    setSelectedCustomerIds((items) => (
      items.includes(customerId)
        ? items.filter((item) => item !== customerId)
        : [...items, customerId]
    ));
  };
  const availableAccounts = accountStatus.accounts?.length
    ? accountStatus.accounts
    : (accountStatus.customer_ids || []).map((customerId, index) => ({
      customer_id: customerId,
      label: `Google Ads ${customerId}`,
      selected_by_default: index === 0,
      status: "NOT_SYNCED",
      status_label: "Not synced",
      publish_eligible: true,
    }));
  const publishableAccounts = availableAccounts.filter((account) => account.publish_eligible !== false);

  return (
    <div className="app-shell min-h-screen text-slate-950">
      <header className="app-header sticky top-0 z-20">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="brand-mark"><Zap size={19} /></div>
            <div>
              <p className="text-base font-black tracking-tight">Campaign AI Studio</p>
              <p className="hidden text-xs font-semibold text-slate-500 sm:block">Content & Google Ads workspace</p>
            </div>
          </div>
          <p className="sidebar-nav-label">Workspace tools</p>
          <nav className="app-nav grid w-full grid-cols-5 gap-1 p-1 text-xs font-black text-slate-600 sm:w-auto" aria-label="Main navigation">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveFlow(item.id)}
                  aria-pressed={activeFlow === item.id}
                  className={`nav-item inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-3 py-2 ${activeFlow === item.id ? "nav-item--active" : ""}`}
                >
                  <Icon size={15} /> <span className="hidden sm:inline">{item.label}</span>
                </button>
              );
            })}
          </nav>
          <div className="sidebar-foot">
            <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-emerald-100 text-emerald-700"><ShieldCheck size={16} /></div>
            <div className="min-w-0">
              <p className="text-xs font-black text-slate-900">Protected publishing</p>
              <p className="mt-0.5 text-[11px] font-semibold leading-4 text-slate-500">Validate content before spending.</p>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1400px] space-y-5 px-4 py-6 sm:px-6 lg:py-8">
        <section className="workspace-hero">
          <div>
            <div className="mb-2 flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-blue-700">
              <Sparkles size={14} /> AI campaign workspace
            </div>
            <h1 className="text-2xl font-black tracking-[-0.035em] text-slate-950 sm:text-3xl">Create campaigns that are ready to perform.</h1>
            <p className="mt-2 max-w-2xl text-sm font-medium leading-6 text-slate-600">
              Turn a landing page into compliant RSA assets, validate every detail, then publish safely across your MCC accounts.
            </p>
          </div>
          <div className="workflow-steps" aria-label="Campaign workflow">
            {[
              ["01", "Generate", "content"],
              ["02", "Review", "deploy"],
              ["03", "Publish", "deploy"],
            ].map(([step, label, flow]) => (
              <button key={`${step}-${label}`} type="button" onClick={() => setActiveFlow(flow)} className={`workflow-step ${activeFlow === flow ? "workflow-step--active" : ""}`}>
                <span>{step}</span>
                <strong>{label}</strong>
              </button>
            ))}
          </div>
        </section>

        <GoogleAdsConnectionBanner accountStatus={accountStatus} onConnect={connectGoogleAds} />
        <WorkspaceOverview accountStatus={accountStatus} selectedCustomerIds={selectedCustomerIds} generated={generated} />

        {error && <div className="whitespace-pre-line rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">{error}</div>}
        {accountSyncNotice && (
          <div className="flex items-start justify-between gap-3 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-800">
            <span className="inline-flex items-start gap-2"><CheckCircle2 className="mt-0.5 shrink-0" size={16} /> {accountSyncNotice}</span>
            <button type="button" onClick={() => setAccountSyncNotice("")} className="shrink-0 text-xs font-black uppercase text-blue-700">Close</button>
          </div>
        )}
        {contentNotice && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-800">{contentNotice}</div>}

        {activeFlow === "content" && (
          <CampaignCsvImport accounts={availableAccounts} onApply={applyCampaignCsvRow} canPublishLive={accountStatus.can_publish_live} />
        )}

        {activeFlow !== "affiliate" && activeFlow !== "history" && activeFlow !== "automation" && <section className="grid items-start gap-5 lg:grid-cols-[420px_1fr]">
          <div className="surface-card p-5 lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:overflow-y-auto">
            <div className="mb-5 flex items-center justify-between gap-3 border-b border-slate-100 pb-4">
              <div className="flex items-center gap-2">
                <Megaphone className="text-blue-600" size={18} />
                <h1 className="text-sm font-black uppercase text-slate-950">RSA Content Inputs</h1>
              </div>
              <span className="rounded-md bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600">Step 1</span>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Landing Page URL" wide>
                <div className="relative">
                  <Link className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                  <input required className={`${inputClass} pl-11`} value={contentForm.landing_page_url} onChange={(event) => updateLandingPageUrl(event.target.value)} />
                </div>
              </Field>
              <Field label="Offer Identity">
                <input className={inputClass} placeholder="Core product promise" value={contentForm.offer_identity} onChange={(event) => updateContentField("offer_identity", event.target.value)} />
              </Field>
              <Field label="Product Name">
                <input className={inputClass} placeholder="Auto-detected if blank" value={contentForm.product_name} onChange={(event) => updateContentField("product_name", event.target.value)} />
              </Field>
              <Field label="High-Intent Keywords" wide>
                <textarea className={textareaClass} placeholder="One keyword per line · auto-extracted if blank" value={contentForm.target_keywords} onChange={(event) => updateContentField("target_keywords", event.target.value)} />
              </Field>
              <Field label="Ad Language">
                <input className={inputClass} value={contentForm.language} onChange={(event) => updateContentField("language", event.target.value)} />
              </Field>
              <Field label="Campaign Tone">
                <input className={inputClass} value={contentForm.tone} onChange={(event) => updateContentField("tone", event.target.value)} />
              </Field>
              <div className="md:col-span-2 border-t border-slate-100 pt-1">
                <p className="text-[10px] font-black uppercase tracking-[0.15em] text-blue-700">Conversion context</p>
                <p className="mt-1 text-xs font-semibold text-slate-500">Leave blank to use signals extracted from the landing page.</p>
              </div>
              <Field label="Target Audience" wide>
                <input className={inputClass} placeholder="Who is most likely to convert?" value={contentForm.target_audience} onChange={(event) => updateContentField("target_audience", event.target.value)} />
              </Field>
              <Field label="Primary Offer">
                <input className={inputClass} placeholder="Trial, discount, guarantee…" value={contentForm.primary_offer} onChange={(event) => updateContentField("primary_offer", event.target.value)} />
              </Field>
              <Field label="Primary CTA">
                <input className={inputClass} placeholder="Start Free Trial" value={contentForm.primary_cta} onChange={(event) => updateContentField("primary_cta", event.target.value)} />
              </Field>
              <Field label="Trust Signals" wide>
                <input className={inputClass} placeholder="Reviews, customers, certification, support…" value={contentForm.trust_signals} onChange={(event) => updateContentField("trust_signals", event.target.value)} />
              </Field>
              <button onClick={generateContent} disabled={loading === "generate" || !contentForm.landing_page_url.trim()} className={`${primaryButton} w-full md:col-span-2`}>
                {loading === "generate" ? <Loader2 className="animate-spin" size={16} /> : <Sparkles size={16} />} Analyze Page & Generate RSA
              </button>
            </div>
          </div>

          <div className="surface-card overflow-hidden p-5">
            <div className="mb-5 flex items-center justify-between gap-3 border-b border-slate-100 pb-4">
              <div>
                <h2 className="text-lg font-black text-slate-950">Publish Workflow</h2>
                <p className="mt-1 text-sm font-semibold text-slate-500">Generate, edit, validate, then publish enabled campaigns to selected MCC accounts.</p>
              </div>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-black text-emerald-700"><ShieldCheck size={13} /> Safe by default</span>
            </div>
            <ExtractionSummary generated={generated} />
            <div className="grid gap-3 md:grid-cols-3">
              <div className="workflow-feature">
                <CheckCircle2 className="text-emerald-600" size={18} />
                <p className="mt-3 text-sm font-black text-slate-950">Character checks</p>
                <p className="mt-1 text-xs font-semibold leading-5 text-slate-500">Headlines and descriptions are checked before publish.</p>
              </div>
              <div className="workflow-feature">
                <Rocket className="text-blue-600" size={18} />
                <p className="mt-3 text-sm font-black text-slate-950">Multi-account push</p>
                <p className="mt-1 text-xs font-semibold leading-5 text-slate-500">Choose one or many Google Ads customer IDs.</p>
              </div>
              <div className="workflow-feature">
                <History className="text-amber-600" size={18} />
                <p className="mt-3 text-sm font-black text-slate-950">Content history</p>
                <p className="mt-1 text-xs font-semibold leading-5 text-slate-500">Used copy and selected account IDs are stored for measurement.</p>
              </div>
            </div>
          </div>
        </section>}

        {activeFlow !== "affiliate" && activeFlow !== "history" && activeFlow !== "automation" && <CreativeAssets generated={generated} onChange={setGenerated} />}

        {activeFlow === "deploy" && (
          <section className="grid gap-6 lg:grid-cols-[1fr_390px]">
            <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-5 flex items-center justify-between gap-3 border-b border-slate-100 pb-4">
                <div className="flex items-center gap-2">
                  <Rocket className="text-blue-600" size={18} />
                  <h2 className="text-sm font-black uppercase text-slate-950">Campaign Setup</h2>
                </div>
                <span className="rounded-md bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600">Step 2</span>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Campaign Name" wide>
                  <input className={inputClass} value={campaignForm.campaign_name} onChange={(event) => {
                    const campaignName = event.target.value;
                    setCampaignForm((current) => ({
                      ...current,
                      campaign_name: campaignName,
                      ad_group_name: !current.ad_group_name.trim() || current.ad_group_name === `${current.campaign_name} - Core`
                        ? `${campaignName} - Core`
                        : current.ad_group_name,
                    }));
                  }} />
                </Field>
                <Field label="Ad Group Name" wide>
                  <input className={inputClass} value={campaignForm.ad_group_name} onChange={(event) => setCampaignForm({ ...campaignForm, ad_group_name: event.target.value })} />
                </Field>
                <Field label="Currency">
                  <select
                    className={inputClass}
                    value={campaignForm.currency_code}
                    onChange={(event) => setCampaignForm({
                      ...campaignForm,
                      currency_code: event.target.value,
                      daily_budget_vnd: event.target.value === "USD" ? 15 : 300000,
                      manual_cpc_bid_vnd: event.target.value === "USD" ? 0.25 : 5000,
                    })}
                  >
                    <option value="VND">VND (₫)</option>
                    <option value="USD">USD ($)</option>
                  </select>
                </Field>
                <Field label={`Daily Budget ${campaignForm.currency_code}`}>
                  <input className={inputClass} type="number" min={campaignForm.currency_code === "USD" ? "2" : "50000"} step={campaignForm.currency_code === "USD" ? "0.01" : "1000"} value={campaignForm.daily_budget_vnd} onChange={(event) => setCampaignForm({ ...campaignForm, daily_budget_vnd: event.target.value })} />
                </Field>
                <Field label={`Manual CPC Bid ${campaignForm.currency_code}`}>
                  <input className={inputClass} type="number" min={campaignForm.currency_code === "USD" ? "0.05" : "1000"} step={campaignForm.currency_code === "USD" ? "0.01" : "100"} value={campaignForm.manual_cpc_bid_vnd} onChange={(event) => setCampaignForm({ ...campaignForm, manual_cpc_bid_vnd: event.target.value })} />
                </Field>
                <Field label="Target Location">
                  <input className={inputClass} value={campaignForm.target_location} onChange={(event) => setCampaignForm({ ...campaignForm, target_location: event.target.value })} />
                </Field>
                <label className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-700 shadow-sm">
                  <input type="checkbox" checked={campaignForm.dry_run} onChange={(event) => setCampaignForm({ ...campaignForm, dry_run: event.target.checked })} />
                  Validate draft first
                </label>
                <label className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-700 shadow-sm">
                  <input type="checkbox" checked={campaignForm.schedule_enabled} onChange={(event) => setCampaignForm({ ...campaignForm, schedule_enabled: event.target.checked })} />
                  Schedule publish time
                </label>
                <div className="md:col-span-2 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                  <p className="text-xs font-black uppercase tracking-[0.12em] text-emerald-800">Campaign networks</p>
                  <div className="mt-3 grid gap-2 text-sm font-bold text-slate-700 sm:grid-cols-3">
                    <label className="flex items-center gap-2">
                      <input type="checkbox" checked readOnly />
                      Google Search
                    </label>
                    <label className="flex items-center gap-2">
                      <input type="checkbox" checked readOnly />
                      Search Partners
                    </label>
                    <label className="flex items-center gap-2 text-slate-500">
                      <input type="checkbox" checked={false} readOnly />
                      Display Network (Off)
                    </label>
                  </div>
                  <p className="mt-2 text-xs font-semibold text-emerald-800">
                    Display expansion is locked off for every draft, scheduled run, and live publish.
                  </p>
                </div>
                <div className="md:col-span-2 flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm font-bold text-amber-950 shadow-sm">
                  <input
                    className="mt-0.5"
                    type="checkbox"
                    checked
                    readOnly
                  />
                  <span>
                    Always enable after publish
                    <span className="mt-1 block text-xs font-semibold leading-5 text-slate-500">
                      The campaign and RSA ad are published as ENABLED and can start spending after Google approves the ad. A final confirmation is required.
                    </span>
                  </span>
                </div>
                {campaignForm.schedule_enabled && (
                  <div className="md:col-span-2 grid gap-4 rounded-lg border border-blue-200 bg-blue-50 p-4 md:grid-cols-2">
                    <Field label="Publish Time">
                      <input
                        className={inputClass}
                        type="datetime-local"
                        value={campaignForm.scheduled_at}
                        onChange={(event) => setCampaignForm({ ...campaignForm, scheduled_at: event.target.value })}
                      />
                    </Field>
                    <Field label="Timezone">
                      <input
                        className={inputClass}
                        value={campaignForm.schedule_timezone}
                        onChange={(event) => setCampaignForm({ ...campaignForm, schedule_timezone: event.target.value })}
                      />
                    </Field>
                    <p className="md:col-span-2 text-xs font-semibold leading-5 text-blue-800">
                      Scheduled campaigns are stored in Publish History with mode scheduled. A scheduler worker is required to auto-publish exactly at that time.
                    </p>
                  </div>
                )}
                <div className="md:col-span-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-xs font-bold uppercase text-slate-500">Publish Accounts</p>
                      <p className="mt-1 text-xs font-semibold text-slate-500">
                        {publishableAccounts.length} active/publishable · {availableAccounts.length} total
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSelectedCustomerIds(
                        selectedCustomerIds.length === publishableAccounts.length
                          ? []
                          : publishableAccounts.map((account) => account.customer_id)
                      )}
                      className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 hover:border-blue-300 hover:text-blue-700"
                    >
                      {selectedCustomerIds.length === publishableAccounts.length ? "Clear All" : "Select Active"}
                    </button>
                  </div>
                  <div className="grid gap-2 md:grid-cols-2">
                    {availableAccounts.map((account) => (
                      <label key={account.customer_id} title={account.status_description || ""} className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm font-bold transition ${account.publish_eligible === false ? "cursor-not-allowed border-slate-200 bg-slate-100 opacity-75" : selectedCustomerIds.includes(account.customer_id) ? "border-blue-300 bg-blue-50 text-blue-900" : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"}`}>
                        <input
                          className="mt-1"
                          type="checkbox"
                          disabled={account.publish_eligible === false}
                          checked={selectedCustomerIds.includes(account.customer_id)}
                          onChange={() => toggleCustomerId(account.customer_id)}
                        />
                        <span className="min-w-0 flex-1">
                          <span className="flex items-start justify-between gap-2">
                            <span className="block truncate text-slate-950">{account.label || `Google Ads ${account.customer_id}`}</span>
                            <AccountStatusBadge account={account} />
                          </span>
                          <span className="mt-1 block text-xs text-slate-400">Customer ID {account.customer_id} · {account.currency_code || "Currency unknown"}</span>
                          <span className="mt-1 block text-[11px] font-semibold text-slate-500">
                            {account.source === "mcc_live" ? "Live MCC" : "Configured"}{account.test_account ? " · Test account" : ""}{account.time_zone ? ` · ${account.time_zone}` : ""}
                          </span>
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
                <Field label="Excluded Locations" wide>
                  <textarea className={textareaClass} placeholder="Location names, one per line" value={campaignForm.excluded_locations} onChange={(event) => setCampaignForm({ ...campaignForm, excluded_locations: event.target.value })} />
                </Field>
                <Field label="Excluded Location IDs" wide>
                  <textarea className={textareaClass} placeholder="Google geo target IDs for live publish" value={campaignForm.excluded_location_ids} onChange={(event) => setCampaignForm({ ...campaignForm, excluded_location_ids: event.target.value })} />
                </Field>
                <button onClick={() => deployCampaign(false)} disabled={Boolean(loading)} className={primaryButton}>
                  {loading === "draft" ? <Loader2 className="animate-spin" size={16} /> : <ShieldCheck size={16} />} Generate & Validate Draft
                </button>
                <button onClick={() => deployCampaign(false, true)} disabled={Boolean(loading) || !campaignForm.schedule_enabled} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
                  {loading === "schedule" ? <Loader2 className="animate-spin" size={16} /> : <History size={16} />} Save Schedule
                </button>
                <button onClick={() => (accountStatus.can_publish_live ? deployCampaign(true) : connectGoogleAds())} disabled={Boolean(loading)} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50">
                  {loading === "publish" ? <Loader2 className="animate-spin" size={16} /> : <Rocket size={16} />} Publish & Enable Campaign
                </button>
              </div>
            </div>

            <aside className="space-y-4">
              <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                <p className="text-sm font-black uppercase text-slate-500">Google Ads Account</p>
                <div className="mt-4 space-y-2 text-sm font-semibold text-slate-600">
                  <p>Manager ID: <span className="text-slate-950">{accountStatus.login_customer_id || "Not set"}</span></p>
                  <p>Selected IDs: <span className="text-slate-950">{selectedCustomerIds.length ? selectedCustomerIds.join(", ") : "None"}</span></p>
                  <p>Configured IDs: <span className="text-slate-950">{(accountStatus.customer_ids || []).join(", ") || accountStatus.customer_id || "Not set"}</span></p>
                  <p>Gmail: <span className="text-slate-950">{accountStatus.google_user?.email || "Not connected"}</span></p>
                  <p>OAuth: <span className={accountStatus.google_oauth_logged_in ? "text-emerald-700" : "text-red-700"}>{accountStatus.google_oauth_logged_in ? "Connected" : "Missing"}</span></p>
                  <p>Ads scope: <span className={accountStatus.google_ads_scope_granted ? "text-emerald-700" : "text-red-700"}>{accountStatus.google_ads_scope_granted ? "Granted" : "Missing"}</span></p>
                  <p>Refresh token: <span className={accountStatus.refresh_token_available ? "text-emerald-700" : "text-red-700"}>{accountStatus.refresh_token_available ? "Available" : "Missing"}</span></p>
                  <p>Live publish: <span className={accountStatus.can_publish_live ? "text-emerald-700" : "text-slate-500"}>{accountStatus.can_publish_live ? "Ready" : "Draft only"}</span></p>
                </div>
                {!accountStatus.can_publish_live && (
                  <button onClick={connectGoogleAds} className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 py-3 text-sm font-bold text-white">
                    <LogIn size={16} /> Connect Gmail Google Ads
                  </button>
                )}
              </div>

              {publishResult && (
                <div className="rounded-lg border border-emerald-200 bg-white p-5 shadow-sm">
                  <p className="text-sm font-black text-emerald-950">{publishResult.message}</p>
                  <div className="mt-4 space-y-2 text-sm font-semibold text-emerald-900">
                    <p>Mode: {publishResult.mode}</p>
                    <p>Accounts: {(publishResult.customer_ids || [publishResult.customer_id]).join(", ")}</p>
                    <p>Network: Google Search + Search Partners · Display Off</p>
                    {publishResult.scheduled_at && <p>Schedule: {new Date(publishResult.scheduled_at).toLocaleString("vi-VN")} ({publishResult.schedule_timezone})</p>}
                    <p>Budget: {formatMoney(publishResult.plan.budget.daily_budget_vnd, publishResult.plan.budget.currency_code)}</p>
                    <p>Manual CPC: {formatMoney(publishResult.plan.bidding.manual_cpc_bid_vnd, publishResult.plan.bidding.currency_code)}</p>
                    <p>Ad Group: {publishResult.plan.ad_group.name}</p>
                    <p>Keywords: {publishResult.plan.ad_group.keywords.map((keyword) => `${keyword.text} (${keyword.match_type})`).join(", ")}</p>
                  </div>
                  <button type="button" onClick={downloadAdsCsv} className="mt-4 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white hover:bg-blue-700">
                    <Download size={16} /> Download Ads CSV
                  </button>
                </div>
              )}
            </aside>
          </section>
        )}

        {activeFlow === "affiliate" && (
          <AffiliateWrapper inputClass={inputClass} primaryButton={primaryButton} onUseProject={selectContentProject} />
        )}

        {activeFlow === "automation" && (
          <DailyAutomation accountStatus={accountStatus} inputClass={inputClass} textareaClass={textareaClass} primaryButton={primaryButton} />
        )}

        {activeFlow === "history" && (
          <PublishHistory primaryButton={primaryButton} />
        )}
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
