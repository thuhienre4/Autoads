import test from "node:test";
import assert from "node:assert/strict";
import { csvRecords, contentIssues, editRow, replaceContent, lines, importedAssets } from "./bulk-content.js";

const valid = { campaign_name: "Example campaign", landing_page_url: "https://example.com", headlines: "First headline\nSecond headline\nThird headline", descriptions: "First description\nSecond description", target_keywords: "example", currency_code: "USD", daily_budget_vnd: "15", manual_cpc_bid_vnd: "0.25", approved: true };
test("CSV retains multiline assets, commas and escaped quotes", () => {
  assert.deepEqual(csvRecords('\uFEFFname,headlines\r\nExample,"First, headline\nSecond ""quoted"" headline"\r\n'), [["\uFEFFname", "headlines"], ["Example", 'First, headline\nSecond "quoted" headline']]);
  assert.throws(() => csvRecords('name\n"unfinished'), /CSV/);
});
test("manual assets are validated before approval", () => {
  assert.deepEqual(contentIssues(valid), []);
  assert.ok(contentIssues({ ...valid, target_keywords: " Example \nexample" }).some(x => x.includes("Keywords: từ khóa trùng")));
  assert.ok(contentIssues({ ...valid, headlines: "x".repeat(31) }).some(x => x.includes("31/30")));
  assert.ok(contentIssues({ ...valid, descriptions: "duplicate\nduplicate" }).some(x => x.includes("trùng")));
  assert.ok(contentIssues({ ...valid, landing_page_url: "javascript:alert(1)" }).some(x => x.includes("URL")));
  assert.ok(contentIssues({ ...valid, daily_budget_vnd: "NaN" }).some(x => x.includes("Ngân sách")));
  assert.ok(contentIssues({ ...valid, schedule_enabled: true, scheduled_at: "2020-01-01" }).some(x => x.includes("tương lai")));
});
test("edits and literal bulk replacements invalidate approval without changing other content", () => {
  assert.equal(replaceContent(valid, "headlines", "missing", "new"), valid);
  assert.equal(replaceContent(valid, "headlines", "headline", "headline"), valid);
  assert.deepEqual(lines("Buy now; explore more | Example"), ["Buy now; explore more | Example"]);
  const edited = editRow(valid, { campaign_name: "Edited" });
  assert.equal(edited.approved, false);
  assert.equal(edited.headlines, valid.headlines);
  const replaced = replaceContent(valid, "headlines", "headline", "$& updated");
  assert.equal(replaced.approved, false);
  assert.equal(replaced.headlines, "First $& updated\nSecond $& updated\nThird $& updated");
  assert.equal(replaced.descriptions, valid.descriptions);
});

test("CSV assets preserve punctuation and numbered column order", () => {
  assert.equal(importedAssets(['description_2', 'description_1'], ['Compare A | B; choose today', 'First; description'], 'descriptions'), 'First; description\nCompare A | B; choose today');
  assert.equal(importedAssets(['descriptions'], ['First; description\nCompare A | B'], 'descriptions'), 'First; description\nCompare A | B');
  assert.equal(importedAssets(['headlines'], ['First|Second|Third'], 'headlines'), 'First\nSecond\nThird');
});
