import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch
from app.services import ai_service as service


class PageContextCacheTests(unittest.TestCase):
    def setUp(self):
        service._page_context_cache.clear()

    @patch.object(service, '_fetch_landing_page_context')
    def test_reuses_context_without_sharing_mutable_values(self, fetch):
        fetch.return_value = {'fetched': True, 'headings': ['Original']}
        first = service._cached_landing_page_context('https://example.com')
        first['headings'].append('Changed')
        second = service._cached_landing_page_context('https://example.com')
        self.assertEqual(second['headings'], ['Original'])
        fetch.assert_called_once()

    @patch.object(service, '_fetch_landing_page_context')
    def test_expiration_and_distinct_urls(self, fetch):
        fetch.return_value = {'fetched': True}
        with patch.object(service, 'monotonic', return_value=0):
            service._cached_landing_page_context('https://example.com/a')
            service._cached_landing_page_context('https://example.com/b')
        with patch.object(service, 'monotonic', return_value=121):
            service._cached_landing_page_context('https://example.com/a')
        self.assertEqual(fetch.call_count, 3)

    @patch.object(service, '_fetch_landing_page_context')
    def test_failures_are_retried(self, fetch):
        fetch.return_value = {'fetched': False, 'error': 'timeout'}
        service._cached_landing_page_context('https://example.com')
        service._cached_landing_page_context('https://example.com')
        self.assertEqual(fetch.call_count, 2)

    @patch.object(service, '_fetch_landing_page_context')
    def test_concurrent_requests_share_one_fetch(self, fetch):
        started, release = Event(), Event()
        def load(url):
            started.set()
            self.assertTrue(release.wait(5))
            return {'fetched': True}
        fetch.side_effect = load
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(service._cached_landing_page_context, 'https://example.com')
            self.assertTrue(started.wait(5))
            second = pool.submit(service._cached_landing_page_context, 'https://example.com')
            release.set()
            self.assertEqual(first.result(), second.result())
        fetch.assert_called_once()
        self.assertFalse(service._page_context_pending)

    @patch.object(service, '_fetch_landing_page_context', return_value={'fetched': True})
    def test_cache_size_is_bounded(self, fetch):
        for index in range(130):
            service._cached_landing_page_context(f'https://example.com/{index}')
        self.assertEqual(len(service._page_context_cache), 128)
