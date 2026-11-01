import hashlib
import io
import json
import unittest
import urllib.error
from tools import runpod_control as control


class ProviderProblemTests(unittest.TestCase):
    def failure(self, body, *, request=None, key='owner-credential', stream=None):
        calls=[]
        def open_request(request, timeout):
            calls.append((request.method, request.full_url))
            raise urllib.error.HTTPError('https://api.runpod.io/v2/pods', 400,
                'untrusted status text', {}, stream or io.BytesIO(body))
        api=control.RunpodAPI(key, opener=open_request)
        with self.assertRaises(control.ProviderError) as observed:
            api.create(request or {'name':'diagnostic-pod'})
        self.assertEqual(calls,[('POST','https://api.runpod.io/v2/pods')])
        self.assertEqual(str(observed.exception),'provider HTTP 400')
        self.assertEqual(observed.exception.http_status,400)
        return observed.exception.problem

    def test_problem_reason_retained_without_retry(self):
        raw=json.dumps({'title':'Bad Request','status':400,
            'detail':'There are no instances available for this configuration.'}).encode()
        result=self.failure(raw)
        self.assertEqual(result['detail'],'There are no instances available for this configuration.')
        self.assertEqual(result['prefix_sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(result['observed_bytes'],len(raw));self.assertFalse(result['truncated'])

    def test_credentials_urls_request_echoes_and_extra_fields_never_survive(self):
        raw=json.dumps({'title':'Bad Request','status':400,
            'detail':'owner-credential https://example.invalid/?signed=very-private request-value abc',
            'errors':['Authorization: Bearer owner-credential', 'environment secret abc',
                      'unknown field from request-value', 'not-retained-fourth-error'],
            'env':{'private':'unexpected-secret'},'request':{'private':'another-secret'}}).encode()
        result=self.failure(raw,request={'name':'request-value','env':{'PASSWORD':'abc'}})
        text=json.dumps(result)
        for secret in ('owner-credential','very-private','request-value','abc','unexpected-secret',
                       'another-secret','not-retained-fourth-error'):
            self.assertNotIn(secret,text)
        self.assertEqual(len(result['errors']),3)
        self.assertIn('[REDACTED_URL]',result['detail'])

    def test_large_invalid_or_wrong_shape_body_never_leaks_content(self):
        for raw,kind in ((b'x'*9000,'TOO_LARGE'),(b'<html>secret</html>','NOT_JSON'),
                         (b'["secret"]','NOT_OBJECT')):
            result=self.failure(raw)
            self.assertEqual(result['body_format'],kind)
            self.assertNotIn('detail',result);self.assertNotIn('secret',json.dumps(result))
            self.assertLessEqual(result['observed_bytes'],8193)

    def test_read_failure_does_not_replace_original_http_failure(self):
        class Broken(io.BytesIO):
            def read(self,n):raise TimeoutError('arbitrary private transport message')
        result=self.failure(b'',stream=Broken())
        self.assertEqual(result,{'schema':'redacted_provider_problem_v1','body_read':'UNAVAILABLE'})

    def test_malformed_problem_fields_and_long_identifiers_are_bounded(self):
        raw=json.dumps({'title':{'unexpected':'secret'},'status':200,
            'detail':'x'*1000,'errors':['short',{'not':'a string'}]}).encode()
        result=self.failure(raw)
        self.assertNotIn('title',result);self.assertNotIn('status',result)
        self.assertEqual(result['detail'],'[REDACTED_IDENTIFIER]')
        self.assertEqual(result['errors'],['short'])

    def test_deep_json_cannot_replace_the_original_http_error(self):
        result=self.failure(b'['*1200+b'0'+b']'*1200)
        self.assertIn(result['body_format'],('NOT_JSON','NOT_OBJECT'))

    def test_short_values_are_redacted_once_and_response_is_closed(self):
        raw=json.dumps({'detail':'R E D'}).encode();stream=io.BytesIO(raw)
        result=self.failure(raw,request={'env':{'a':'R','b':'E','c':'D'}},stream=stream)
        self.assertEqual(result['detail'],'[REDACTED] [REDACTED] [REDACTED]')
        self.assertTrue(stream.closed)


if __name__=='__main__':unittest.main()
