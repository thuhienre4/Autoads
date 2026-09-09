import test from 'node:test';
import assert from 'node:assert/strict';
import { deploymentMode } from './campaign-draft.js';

test('validation never enables live publishing', () => {
  assert.deepEqual(deploymentMode(), { schedule_enabled: false, dry_run: true, enable_immediately: false });
});
test('publish explicitly enables immediate delivery', () => {
  assert.deepEqual(deploymentMode(true), { schedule_enabled: false, dry_run: false, enable_immediately: true });
});
test('schedule persists a scheduled deployment', () => {
  assert.deepEqual(deploymentMode(false, true), { schedule_enabled: true, dry_run: false, enable_immediately: true });
});
