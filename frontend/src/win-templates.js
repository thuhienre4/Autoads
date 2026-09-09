export const exampleTemplate = {
  name: "Mẫu lợi ích + CTA",
  notes: "Mở đầu bằng lợi ích, kết thúc bằng lời kêu gọi hành động ngắn.",
  headlines: ["Simplify Your Workflow", "Save Time Every Day", "Explore Acme Today"],
  descriptions: ["Keep your work organized in one place. Explore Acme today.", "Find the right tools for your team. See features and plans."],
};

export const assetLines = (text) => text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);

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
