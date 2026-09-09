import test from 'node:test';
import assert from 'node:assert/strict';
import { accountGroup } from './account-health.js';
test('classifies live account states separately', () => {
  for (const [status, group] of [['SUSPENDED', 'suspended'], ['ENABLED', 'enabled'], ['CANCELED', 'inactive'], ['CLOSED', 'inactive'], ['UNKNOWN', 'unknown']]) {
    assert.equal(accountGroup({status, source: 'mcc_live'}), group);
  }
});
test('cached and unsynced accounts cannot be classified as healthy', () => {
  assert.equal(accountGroup({status: 'ENABLED'}), 'unknown');
  assert.equal(accountGroup({status: 'ENABLED', source: 'mcc_live'}, true), 'unknown');
});
