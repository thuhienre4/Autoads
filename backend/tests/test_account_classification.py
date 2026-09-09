import unittest
from app.services.account_diagnostics import classify_report

class AccountClassificationTests(unittest.TestCase):
    def report(self, **values):
        return dict(dict(account_source='mcc_live', sync_error=None, status='ENABLED', campaigns_checked=True, api_errors=[], truncated=False, campaigns=[dict(status='ENABLED', primary_status='ELIGIBLE', reasons=[])]), **values)

    def test_clean_checked_account(self):
        self.assertEqual(classify_report(self.report())['code'], 'no_issues_detected')

    def test_suspension_is_distinct_from_paused_campaign(self):
        self.assertEqual(classify_report(self.report(status='SUSPENDED', campaigns_checked=False))['code'], 'suspended')
        paused = [dict(status='PAUSED', primary_status='PAUSED', reasons=[dict(code='CAMPAIGN_PAUSED')])]
        self.assertEqual(classify_report(self.report(campaigns=paused))['code'], 'paused_campaigns')

    def test_incomplete_or_stale_data_never_passes(self):
        for values in [dict(sync_error='timeout'), dict(account_source='mcc_cache'), dict(campaigns_checked=False), dict(truncated=True), dict(api_errors=[{'message': 'denied'}]), dict(status='UNKNOWN')]:
            with self.subTest(values=values):
                self.assertEqual(classify_report(self.report(**values))['code'], 'unknown')

    def test_policy_problem_and_empty_account_are_not_clean(self):
        campaigns = [dict(status='ENABLED', primary_status='NOT_ELIGIBLE', reasons=[dict(code='HAS_ADS_DISAPPROVED')])]
        self.assertEqual(classify_report(self.report(campaigns=campaigns))['code'], 'attention')
        self.assertEqual(classify_report(self.report(campaigns=[]))['code'], 'no_campaigns')
