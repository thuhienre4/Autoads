// Advisory rules reviewed against Google Ads policy pages on 2026-09-05.
const sources = {
  editorial: "https://support.google.com/adspolicy/answer/6021546",
  claims: "https://support.google.com/adspolicy/answer/6020955",
  destination: "https://support.google.com/adspolicy/answer/6368661",
};
const rules = [
  { id: "claims", pattern: /\bguaranteed\s+(?:results?|income|profits?|returns?)\b|\b(?:cure|cures)\b|chữa khỏi|cam kết (?:lợi nhuận|thu nhập|khỏi bệnh)|(?:giảm cân|lose weight).{0,30}(?:\d+\s*(?:ngày|days?)|tức thì)/iu,
    title: "Tuyên bố kết quả cần kiểm chứng", fix: "Bỏ cam kết kết quả chắc chắn; mô tả đúng lợi ích có bằng chứng và điều kiện áp dụng.", source: "claims" },
  { id: "affiliation", pattern: /\bofficial\b|chính thức|được google (?:chứng nhận|bảo trợ)|google[- ]certified/iu,
    title: "Cần xác minh quan hệ với thương hiệu", fix: "Chỉ giữ tuyên bố chính thức/chứng nhận khi có quyền và bằng chứng. Nếu là bên giới thiệu, mô tả đúng vai trò.", source: "claims" },
  { id: "offer", pattern: /\bfree\b|miễn phí|\d+\s*%\s*(?:off|discount)|giảm\s*\d+\s*%/iu,
    title: "Cần đối chiếu ưu đãi", fix: "Kiểm tra ưu đãi còn hiệu lực, điều kiện và mọi khoản phí trên trang đích. Từ này tự nó không phải vi phạm.", source: "claims" },
  { id: "punctuation", pattern: /[!?]{2,}|[★☆]{2,}/u,
    title: "Dấu câu/ký hiệu lặp", fix: "Dùng dấu câu thông thường, bỏ ký hiệu dùng để gây chú ý.", source: "editorial", adOnly: true },
  { id: "phone", pattern: /(?:\+\d{1,3}[ .-]?)?(?:\(?\d{3}\)?[ .-]){2}\d{4}|\b0\d{9}\b/u,
    title: "Có thể chứa số điện thoại trong mẫu quảng cáo", fix: "Nếu đây là số điện thoại, chuyển sang thành phần cuộc gọi thay vì đặt trong headline/description.", source: "editorial", adOnly: true },
];

export function reviewPolicy(assets = {}, landingPageUrl = "") {
  const findings = [];
  const add = (id, field, evidence, title, fix, source) => findings.push({ id: `${field}-${id}`, field, evidence, title, fix, url: sources[source] });
  const fields = [
    ...(assets.headlines || []).map((text, i) => ({ field: `Headline ${i + 1}`, text })),
    ...(assets.descriptions || []).map((text, i) => ({ field: `Description ${i + 1}`, text })),
  ];
  const page = assets.landing_page_alignment?.page_context;
  if (page?.fetched) {
    fields.push({ field: "Landing page (bản trích)", text: [page.title, page.meta_description, ...(page.headings || []), page.body_excerpt].filter(Boolean).join("\n"), page: true });
  }
  for (const item of fields) {
    const text = String(item.text || "");
    for (const rule of rules) {
      if (item.page && rule.adOnly) continue;
      const match = text.match(rule.pattern);
      if (match) add(rule.id, item.field, match[0], rule.title, rule.fix, rule.source);
    }
    const letters = text.replace(/[^\p{L}]/gu, "");
    if (!item.page && letters.length >= 10 && letters === letters.toUpperCase() && letters !== letters.toLowerCase()) {
      add("caps", item.field, text, "Toàn bộ nội dung viết hoa", "Dùng cách viết hoa thông thường; kiểm tra ngoại lệ cho tên thương hiệu hoặc chữ viết tắt.", "editorial");
    }
  }
  let validUrl = false;
  try { validUrl = ["http:", "https:"].includes(new URL(landingPageUrl).protocol); } catch { /* Show missing/invalid URL below. */ }
  if (!validUrl) add("url", "Landing page", landingPageUrl || "Chưa nhập URL", "Chưa có URL web hợp lệ", "Nhập URL đầy đủ bắt đầu bằng https:// hoặc http://.", "destination");
  return { findings, pageReviewed: Boolean(page?.fetched), checkedAssets: fields.filter((item) => !item.page).length };
}
