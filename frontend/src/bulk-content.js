export const lines = value => String(value || "").split(/\r?\n/).map(x => x.trim()).filter(Boolean);

// Numbered columns hold individual assets. Multiline cells preserve punctuation;
// single-line list cells also accept the legacy pipe separator from our template.
export function importedAssets(headers, cells, field) {
  const combined = String(cells[headers.indexOf(field)] || "").trim();
  if (combined) return (/\r?\n/.test(combined) ? lines(combined) : combined.split('|').map(x => x.trim()).filter(Boolean)).join('\n');
  const singular = field === 'headlines' ? 'headline' : 'description';
  return headers.map((header, index) => ({ match: header.match(new RegExp(`^${singular}[ _](\\d+)$`)), value: cells[index] }))
    .filter(item => item.match && String(item.value || '').trim())
    .sort((a, b) => Number(a.match[1]) - Number(b.match[1]))
    .map(item => String(item.value).trim()).join('\n');
}

export function csvRecords(text) {
  const records = []; let row = [], cell = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') {
      if (quoted && text[i + 1] === '"') { cell += '"'; i++; }
      else quoted = !quoted;
    } else if (c === ',' && !quoted) { row.push(cell); cell = ""; }
    else if ((c === '\n' || c === '\r') && !quoted) {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(cell); if (row.some(x => x.trim())) records.push(row);
      row = []; cell = "";
    } else cell += c;
  }
  if (quoted) throw new Error("CSV có dấu ngoặc kép chưa đóng.");
  row.push(cell); if (row.some(x => x.trim())) records.push(row);
  return records;
}

export function contentIssues(row) {
  const issues = [];
  try { const url = new URL(row.landing_page_url); if (!["https:", "http:"].includes(url.protocol) || !url.hostname.includes('.')) throw Error(); }
  catch { issues.push("URL: cần địa chỉ http/https hợp lệ"); }
  if (String(row.campaign_name || "").trim().length < 3) issues.push("Tên campaign: tối thiểu 3 ký tự");
  for (const [field, label, min, max, limit] of [["headlines", "Headline", 3, 15, 30], ["descriptions", "Description", 2, 4, 90]]) {
    const values = lines(row[field]);
    if (values.length < min || values.length > max) issues.push(`${label}: cần ${min}–${max} dòng`);
    values.forEach((v, i) => { if ([...v].length > limit) issues.push(`${label} ${i + 1}: ${[...v].length}/${limit} ký tự`); });
    if (new Set(values.map(v => v.toLowerCase())).size !== values.length) issues.push(`${label}: nội dung trùng lặp`);
  }
  const keywords = lines(row.target_keywords);
  if (!keywords.length) issues.push("Keywords: cần ít nhất một từ khóa");
  if (new Set(keywords.map(keyword => keyword.toLowerCase())).size !== keywords.length) issues.push("Keywords: từ khóa trùng lặp, hãy xóa bản trùng trước khi duyệt");
  const minimums = row.currency_code === "USD" ? [2, 0.05] : [50000, 1000];
  for (const [field, min, label] of [["daily_budget_vnd", minimums[0], "Ngân sách"], ["manual_cpc_bid_vnd", minimums[1], "CPC"]]) {
    if (!Number.isFinite(Number(row[field])) || Number(row[field]) < min) issues.push(`${label}: tối thiểu ${min} ${row.currency_code || ""}`);
  }
  if (row.schedule_enabled && (!row.scheduled_at || !Number.isFinite(Date.parse(row.scheduled_at)) || Date.parse(row.scheduled_at) <= Date.now())) issues.push("Lịch đăng phải ở tương lai");
  return issues;
}

export function editRow(row, patch) {
  return { ...row, ...patch, approved: false, suggestion: null, result: null, errors: [] };
}

export function replaceContent(row, field, search, replacement) {
  if (!search) return row;
  const original = String(row[field] || "");
  const next = original.split(search).join(replacement);
  return next === original ? row : editRow(row, { [field]: next });
}
