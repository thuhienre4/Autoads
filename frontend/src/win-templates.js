export const exampleTemplate = {
  name: "Mẫu lợi ích + CTA",
  notes: "Mở đầu bằng lợi ích, kết thúc bằng lời kêu gọi hành động ngắn.",
  headlines: ["Simplify Your Workflow", "Save Time Every Day", "Explore Acme Today"],
  descriptions: ["Keep your work organized in one place. Explore Acme today.", "Find the right tools for your team. See features and plans."],
};

export const assetLines = (text) => text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);

export const templatePayload = (draft) => ({ name: draft.name.trim(), notes: draft.notes.trim(), headlines: assetLines(draft.headlines), descriptions: assetLines(draft.descriptions) });

export function templateReviewCurrent(value, assets) {
  return value?.verification?.status === "reviewed" && ["headlines", "descriptions"].every(field =>
    Array.isArray(value.grounding?.[field]) && Array.isArray(assets?.[field]) && assets[field].length > 0
    && JSON.stringify(value.grounding[field].map(asset => asset.text)) === JSON.stringify(assets[field]));
}

export function winDraftIssues(draft) {
  const issues = [];
  if (!draft.name.trim() || draft.name.trim().length > 120) issues.push("Tên mẫu cần 1–120 ký tự.");
  if (draft.notes.trim().length > 2000) issues.push("Ghi chú tối đa 2.000 ký tự.");
  for (const [field, label, max, limit] of [["headlines", "Headline", 15, 30], ["descriptions", "Description", 4, 90]]) {
    const values = assetLines(draft[field]);
    if (!values.length || values.length > max) issues.push(`${label}: cần 1–${max} dòng.`);
    if (values.some(value => [...value].length > limit)) issues.push(`${label}: tối đa ${limit} ký tự/dòng.`);
    if (values.some(value => value.startsWith("="))) issues.push(`${label}: thay công thức bằng văn bản.`);
    if (new Set(values.map(value => value.toLowerCase())).size !== values.length) issues.push(`${label}: có nội dung trùng.`);
  }
  return issues;
}

export function parseWinFile(text, filename) {
  text = text.replace(/^\uFEFF/, "");
  if (/\.json$/i.test(filename)) {
    const data = JSON.parse(text);
    if (!data || typeof data !== "object" || Array.isArray(data) || typeof data.name !== "string" || !Array.isArray(data.headlines) || !Array.isArray(data.descriptions)
      || [...data.headlines, ...data.descriptions].some((item) => typeof item !== "string") || (data.notes != null && typeof data.notes !== "string")) {
      throw new Error("JSON cần name, headlines và descriptions (mảng chuỗi), notes tùy chọn.");
    }
    return { name: data.name, notes: data.notes || "", headlines: data.headlines.join("\n"), descriptions: data.descriptions.join("\n") };
  }
  if (!/\.txt$/i.test(filename)) throw new Error("Chọn file .txt hoặc .json.");
  const result = { name: filename.replace(/\.txt$/i, ""), notes: "", headlines: [], descriptions: [] };
  let section = "";
  for (const line of assetLines(text)) {
    const heading = line.match(/^\[?(headlines|descriptions)\]?:?$/i);
    if (heading) { section = heading[1].toLowerCase(); continue; }
    if (!section) throw new Error("TXT cần tiêu đề [Headlines] và [Descriptions], mỗi nội dung một dòng.");
    result[section].push(line);
  }
  if (!result.headlines.length || !result.descriptions.length) throw new Error("File cần cả headline và description.");
  return { ...result, headlines: result.headlines.join("\n"), descriptions: result.descriptions.join("\n") };
}
