import concurrent.futures
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
import unittest

from tools.research_meter import Ledger, Rejected, gateway, token_usage


def request(**values):
    body = {'model': 'frozen-model', 'temperature': 0.2, 'top_p': 0.95, 'max_tokens': 16384,
            'chat_template_kwargs': {'enable_thinking': True}, 'messages': [{'role': 'user', 'content': 'fixture'}]}
    body.update(values)
    return json.dumps(body).encode()


def response(usage=None):
    return json.dumps({'usage': usage or {'prompt_tokens': 11, 'completion_tokens': 7, 'total_tokens': 18,
        'completion_tokens_details': {'reasoning_tokens': 3}}}).encode()


class UsageTests(unittest.TestCase):
    def test_exact_counts_reasoning_not_added_twice(self):
        row = token_usage(response(), False)
        self.assertEqual(row['total_tokens'], 18)
        self.assertEqual(row['reasoning_tokens'], 3)
        self.assertIsNone(row['cached_tokens'])

    def test_stream_terminal_usage_counted_once(self):
        data = b'data: {"usage":null,"choices":[]}\n\ndata: ' + response() + b'\n\ndata: [DONE]\n\n'
        self.assertEqual(token_usage(data, True)['total_tokens'], 18)

    def test_truncated_duplicate_and_malformed_usage_remain_unknown(self):
        samples = [(b'{}', False), (b'data: ' + response() + b'\n\n', True),
                   (b'data: ' + response() + b'\n\ndata: ' + response() + b'\n\ndata: [DONE]\n', True),
                   (response({'prompt_tokens': True, 'completion_tokens': 7, 'total_tokens': 8}), False),
                   (response({'prompt_tokens': 11, 'completion_tokens': 7, 'total_tokens': 3}), False),
                   (response({'prompt_tokens': 11, 'completion_tokens': 7, 'total_tokens': 18,
                              'completion_tokens_details': {'reasoning_tokens': 8}}), False)]
        for data, streaming in samples:
            with self.subTest(data=data):
                actual = token_usage(data, streaming)
                self.assertEqual(actual['status'], 'MISSING_OR_INVALID')
                self.assertIsNone(actual['total_tokens'])


class LedgerTests(unittest.TestCase):
    def test_deadline_uses_exact_official_session_start(self):
        now = [101.0]; ledger = Ledger('frozen-model', clock=lambda: now[0])
        ledger.start(100.0)
        self.assertEqual(ledger.deadline, 400.0)
        now[0] = 400.0
        with self.assertRaises(Rejected): ledger.admit(request())
        for timestamp in (401.0, 300.0, float('nan')):
            fresh = Ledger('frozen-model', clock=lambda: now[0])
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError): fresh.start(timestamp)

    def test_concurrent_root_delegate_and_retry_attempts_share_fifty(self):
        ledger = Ledger('frozen-model'); ledger.start()
        def call(i):
            try:
                n, _ = ledger.admit(request(messages=[{'role': 'user', 'content': str(i)}]))
                ledger.finish(n, 500 if i % 3 == 0 else 200, response())
                return True
            except Rejected:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            self.assertEqual(sum(pool.map(call, range(80))), 50)
        report = ledger.report()
        self.assertEqual(report['admitted_requests'], 50)
        self.assertEqual(report['rejected_requests'], 30)
        self.assertEqual(report['totals']['total_tokens'], 900)
        self.assertEqual({r['request'] for r in report['requests']}, set(range(1, 51)))

    def test_failed_and_unfinished_requests_prevent_complete_token_claim(self):
        ledger = Ledger('frozen-model'); ledger.start()
        n, _ = ledger.admit(request()); ledger.finish(n, 500, b'{"error":"fixture"}')
        ledger.admit(request())
        self.assertEqual(ledger.report()['token_accounting'], 'INCOMPLETE')
        self.assertIsNone(ledger.report()['totals']['prompt_tokens'])

    def test_work_deadline_never_becomes_teardown_allowance(self):
        now = [100.0]; ledger = Ledger('frozen-model', clock=lambda: now[0])
        with self.assertRaises(Rejected): ledger.admit(request())
        ledger.start(); now[0] = 399.9
        ledger.admit(request()); now[0] = 400
        with self.assertRaises(Rejected): ledger.admit(request())
        with self.assertRaises(ValueError): ledger.start()

    def test_new_task_requires_new_ledger_and_close_is_terminal(self):
        first = Ledger('frozen-model'); first.start(); first.admit(request()); first.close()
        with self.assertRaises(Rejected): first.admit(request())
        second = Ledger('frozen-model'); second.start()
        self.assertEqual(second.admit(request())[0], 1)

    def test_sampling_drift_rejected_before_upstream(self):
        ledger = Ledger('frozen-model'); ledger.start()
        for changes in ({'model': 'wrong'}, {'temperature': 1}, {'top_p': 1}, {'max_tokens': 20000},
                        {'n': 2}, {'chat_template_kwargs': {'enable_thinking': False}}):
            with self.subTest(changes=changes), self.assertRaises(Rejected): ledger.admit(request(**changes))
        self.assertEqual(ledger.report()['admitted_requests'], 0)

    def test_stream_usage_requested_and_content_not_in_public_receipt(self):
        ledger = Ledger('frozen-model'); ledger.start()
        n, body = ledger.admit(request(stream=True))
        self.assertEqual(json.loads(body)['stream_options'], {'include_usage': True})
        self.assertNotIn('fixture', json.dumps(ledger.report()))
        ledger.finish(n, 200, response())
        with self.assertRaises(ValueError): ledger.finish(n, 200, response())


class GatewayTests(unittest.TestCase):
    def test_actual_http_error_retry_stream_and_hard_limit(self):
        calls = []
        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append(value)
                self.send_response(500 if len(calls) == 1 else 200)
                if value.get('stream'):
                    data = b'data: ' + response() + b'\n\ndata: [DONE]\n\n'
                    self.send_header('Content-Type', 'text/event-stream')
                else:
                    data = response()
                    self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        ledger = Ledger('frozen-model', limit=3); ledger.start()
        try:
            with gateway(ledger, server.server_port) as port:
                statuses = []
                for index in range(5):
                    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
                    connection.request('POST', '/v1/chat/completions', body=request(stream=index == 2))
                    result = connection.getresponse(); statuses.append(result.status); result.read(); connection.close()
            self.assertEqual(statuses, [500, 200, 200, 400, 400])
            self.assertEqual(len(calls), 3)
            self.assertEqual(ledger.report()['totals']['total_tokens'], 54)
            self.assertTrue(ledger.report()['closed'])
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_inflight_stall_terminated_at_work_deadline(self):
        class Slow(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                time.sleep(.2)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Slow)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        ledger = Ledger('frozen-model', seconds=.05); ledger.start()
        try:
            with gateway(ledger, server.server_port) as port:
                connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
                connection.request('POST', '/v1/chat/completions', body=request())
                with self.assertRaises(http.client.RemoteDisconnected): connection.getresponse()
                connection.close()
            report = ledger.report()
            self.assertEqual(report['admitted_requests'], 1)
            self.assertEqual(report['token_accounting'], 'INCOMPLETE')
            self.assertEqual(report['requests'][0]['transport_error'], 'TimeoutError')
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': unittest.main()
