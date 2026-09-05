import test from "node:test";
import assert from "node:assert/strict";
import { reviewPolicy } from "./policy-review.js";

test("flags specific risky claims and clears after edits", () => {
  const report = reviewPolicy({ headlines: ["Guaranteed profits", "Cam kết lợi nhuận"] }, "https://example.com");
  assert.equal(report.findings.filter((item) => item.id.endsWith("claims")).length, 2);
  assert.equal(report.findings[0].field, "Headline 1");
  assert.equal(report.findings[0].evidence, "Guaranteed profits");
  assert.equal(reviewPolicy({ headlines: ["Explore Our Services"] }, "https://example.com").findings.length, 0);
});

test("ordinary guarantee and acronym do not trigger broad claims or caps flags", () => {
  const report = reviewPolicy({ headlines: ["30-Day Money-Back Guarantee", "CRM for Teams"] }, "https://example.com");
  assert.equal(report.findings.length, 0);
});

test("checks offers, punctuation, and capitalization separately", () => {
  const report = reviewPolicy({ headlines: ["FREE DELIVERY!!"] }, "https://example.com");
  for (const id of ["offer", "punctuation", "caps"]) assert.ok(report.findings.some((item) => item.id.endsWith(id)));
});

test("only inspects fetched page excerpts and reports incomplete coverage", () => {
  const page = { fetched: true, body_excerpt: "Guaranteed returns", title: "Example" };
  const assets = { landing_page_alignment: { page_context: page } };
  assert.equal(reviewPolicy(assets, "https://example.com").findings.length, 1);
  page.fetched = false;
  const report = reviewPolicy(assets, "https://example.com");
  assert.equal(report.pageReviewed, false);
  assert.equal(report.findings.length, 0);
});

test("rejects non-web and missing destinations without crashing", () => {
  for (const url of ["", "javascript:alert(1)", "example.com"]) {
    assert.ok(reviewPolicy({}, url).findings.some((item) => item.id.endsWith("url")));
  }
});
