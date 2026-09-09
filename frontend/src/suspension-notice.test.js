import test from 'node:test';
import assert from 'node:assert/strict';
import { analyzeNotice } from './suspension-notice.js';

test('recognizes English and Vietnamese notices and multiple mentioned issues', () => {
  assert.deepEqual(analyzeNotice('Suspicious payment activity; Circumventing Systems').map(x => x.code), ['circumventing', 'payments']);
  assert.equal(analyzeNotice('THANH TOÁN ĐÁNG NGỜ'.normalize('NFD'))[0].code, 'payments');
});
test('does not infer a specific reason from suspension or campaign pause alone', () => {
  for (const text of ['', 'SUSPENDED', 'Tài khoản bị tạm ngưng', 'Campaign paused']) assert.deepEqual(analyzeNotice(text), []);
});
