import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from app.services import account_diagnostics as d
from google.ads.googleads.v21.services.types.identity_verification_service import GetIdentityVerificationResponse

class VerificationTests(unittest.TestCase):
    def setUp(self):
        d._verification_cache.clear()

    def test_actual_proto_fields_and_cache(self):
        response = GetIdentityVerificationResponse(identity_verification=[{
            'verification_program': 'ADVERTISER_IDENTITY_VERIFICATION',
            'verification_progress': {'program_status': 'PENDING_USER_ACTION'},
            'identity_verification_requirement': {'verification_completion_deadline_time': '2026-10-01 00:00:00'},
        }])
        with patch.object(d, 'build_google_ads_client') as client:
            service = client.return_value.get_service.return_value
            service.get_identity_verification.return_value = response
            first = d.read_verification('123')
            second = d.read_verification('123')
            service.get_identity_verification.assert_called_once_with(customer_id='123', timeout=20)
        self.assertTrue(first['checked'])
        self.assertFalse(first['pause_confirmed'])
        self.assertEqual(first['programs'][0]['status'], 'PENDING_USER_ACTION')
        self.assertEqual(first, second)
        second['programs'].clear()
        self.assertTrue(d.read_verification('123')['programs'])

    def test_failed_read_is_unknown(self):
        with patch.object(d, 'build_google_ads_client', side_effect=RuntimeError('secret')):
            result = d.read_verification('123')
        self.assertFalse(result['checked'])
        self.assertNotIn('secret', str(result))

    def test_empty_response_is_not_success(self):
        with patch.object(d, 'build_google_ads_client') as client:
            client.return_value.get_service.return_value.get_identity_verification.return_value = GetIdentityVerificationResponse()
            result = d.read_verification('123')
        self.assertTrue(result['checked'])
        self.assertEqual(result['programs'], [])

    def test_verification_does_not_override_suspension(self):
        report = dict(account_source='mcc_live', sync_error=None, status='SUSPENDED', verification={'checked': True, 'programs': [{'status': 'PENDING_USER_ACTION'}]})
        self.assertEqual(d.classify_report(report)['code'], 'suspended')
        report['status'] = 'ENABLED'
        self.assertEqual(d.classify_report(report)['code'], 'verification_attention')
