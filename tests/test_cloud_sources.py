import json
import unittest
from tools import cloud_sources as sources


class SourceLifetimeTests(unittest.TestCase):
    def test_gcs_v4_uses_utc_and_reports_insufficient_window_without_secrets(self):
        url = ('https://storage.googleapis.com/private/model?X-Goog-Date=20261022T120000Z'
               '&X-Goog-Expires=3600&X-Goog-Signature=PRIVATE-CANARY')
        kind, deadline = sources.expiry(url)
        self.assertEqual(kind, 'GCS_V4')
        result = sources.snapshot({'model': {'weights': {'url': url}}}, now=deadline-3500)
        self.assertEqual(result['streams']['model']['minimum_declared_remaining_seconds'], 3500)
        self.assertEqual(result['streams']['model']['shorter_than_setup_window'], 1)
        self.assertNotIn('PRIVATE-CANARY', json.dumps(result))
        self.assertNotIn('storage.googleapis.com', json.dumps(result))

    def test_expired_duplicate_and_unknown_signatures_never_become_validity_proof(self):
        url = 'https://storage.googleapis.com/private/model?Expires=100&Signature=PRIVATE-CANARY'
        self.assertEqual(sources.expiry(url), ('GCS_V2', 100))
        self.assertEqual(sources.snapshot({'model': {'x': {'url': url}}}, now=101)['streams']['model']['expired'], 1)
        for extra in ('&Expires=200', '&X-Goog-Expires=3600'):
            self.assertEqual(sources.expiry(url+extra), ('UNVERIFIABLE', None))
        self.assertEqual(sources.expiry('https://www.kaggleusercontent.com/private?opaque=token'),
                         ('UNVERIFIABLE', None))

    def test_public_host_without_query_is_distinct_from_unknown_private_lifetime(self):
        self.assertEqual(sources.expiry('https://files.pythonhosted.org/pkg.whl'),
                         ('PUBLIC_NO_DECLARED_EXPIRY', None))
        self.assertEqual(sources.expiry('https://storage.googleapis.com/object'), ('UNVERIFIABLE', None))
        with self.assertRaises(ValueError): sources.expiry('https://unexpected.invalid/model')


if __name__ == '__main__': unittest.main()
