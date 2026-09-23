import test from 'node:test';
import assert from 'node:assert/strict';
import { historyToDraft } from './history-draft.js';

test('reuses saved content and targeting with editable account IDs and a fresh schedule', () => {
  const item = {
    campaign_name: 'Saved campaign', ad_group_name: 'Saved group',
    landing_page_url: 'https://example.com', customer_ids: ['1234567890'],
    target_location: 'United States',
    budget: { daily_budget_vnd: 25, manual_cpc_bid_vnd: 0.5, currency_code: 'USD' },
    content: { keywords: ['buy shoes'], headlines: ['Saved headline'], descriptions: ['Saved description'] },
    schedule: { enabled: true, scheduled_at: '2020-01-01', timezone: 'UTC' },
    plan: { campaign: { excluded_locations: ['Alaska'], excluded_location_ids: [123], networks: { search_partners: false, display_network: true } },
      ad_group: { keywords: [{ text: 'buy shoes', match_type: 'PHRASE' }, { text: 'buy shoes', match_type: 'EXACT' }] } },
  };
  const before = structuredClone(item);
  const draft = historyToDraft(item);
  assert.equal(draft.contentForm.target_keywords, 'buy shoes');
  assert.equal(draft.campaignForm.manual_cpc_bid_vnd, 0.5);
  assert.equal(draft.campaignForm.currency_code, 'USD');
  assert.equal(draft.campaignForm.excluded_location_ids, '123');
  assert.deepEqual(draft.campaignForm.keyword_match_types, ['PHRASE', 'EXACT']);
  assert.equal(draft.campaignForm.search_partners, false);
  assert.equal(draft.campaignForm.display_network, true);
  assert.equal(draft.campaignForm.schedule_enabled, false);
  assert.equal(draft.campaignForm.scheduled_at, '');
  assert.equal(draft.campaignForm.dry_run, true);
  draft.selectedCustomerIds[0] = '9876543210';
  draft.generated.headlines[0] = 'Edited headline';
  assert.deepEqual(item, before);
});

test('older history without optional setup loads with defaults', () => {
  const draft = historyToDraft({ content: { headlines: ['Old headline'] } });
  assert.deepEqual(draft.generated.headlines, ['Old headline']);
  assert.deepEqual(draft.generated.descriptions, []);
  assert.deepEqual(draft.campaignForm.keyword_match_types, ['EXACT']);
  assert.deepEqual(draft.selectedCustomerIds, []);
});
