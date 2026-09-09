import test from "node:test";
import assert from "node:assert/strict";
import { parseWinFile, exampleTemplate, winDraftIssues, templatePayload } from "./win-templates.js";

test("JSON sample and BOM import preserve Vietnamese and asset order", () => {
  const draft = parseWinFile("\uFEFF" + JSON.stringify(exampleTemplate), "win.json");
  assert.equal(draft.name, exampleTemplate.name);
  assert.equal(draft.headlines, exampleTemplate.headlines.join("\n"));
});
test("TXT section import handles CRLF and punctuation", () => {
  const draft = parseWinFile("[Headlines]\r\nLàm việc hiệu quả\r\n[Descriptions]\r\nXem tính năng: bắt đầu ngay.\r\n", "my-win.txt");
  assert.equal(draft.headlines, "Làm việc hiệu quả");
  assert.equal(draft.descriptions, "Xem tính năng: bắt đầu ngay.");
});
test("unsupported or malformed uploads do not replace a draft", () => {
  for (const [text, name] of [["{}", "bad.json"], ["{}", "bad.csv"], ["[Headlines]\nOnly headline", "bad.txt"], ['{"name":"X","headlines":[4],"descriptions":["D"]}', "bad.json"]]) {
    assert.throws(() => parseWinFile(text, name));
  }
});

test("reviewed drafts validate and only template fields are saved", () => {
  const draft = { name: " New ", notes: " Note ", headlines: "Headline A\nHeadline B", descriptions: "Description", source: "file.xlsx", selected: true };
  assert.deepEqual(winDraftIssues(draft), []);
  assert.deepEqual(templatePayload(draft), { name: "New", notes: "Note", headlines: ["Headline A", "Headline B"], descriptions: ["Description"] });
  assert.ok(winDraftIssues({ ...draft, headlines: "Duplicate\nDuplicate" }).length);
  assert.ok(winDraftIssues({ ...draft, descriptions: "x".repeat(91) }).length);
  assert.ok(winDraftIssues({ ...draft, headlines: "=1+1" }).length);
});
