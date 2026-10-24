"""One-task loopback HTTP gate: every retry/delegate spends the same allowance.

This is an accounting boundary, not an OS network sandbox. Deployment must
prevent direct access to the upstream. It never allocates or starts a model.
"""
import contextlib
import copy
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import threading
import time

from tools.research_comparison import parse

BODY_LIMIT = 8 * 1024**2
RESPONSE_LIMIT = 16 * 1024**2


def token_usage(data, streaming):
    """Count a final cumulative usage object once; never substitute zeros."""
    try:
        if streaming:
            lines = data.decode('utf-8').replace('\r\n', '\n').split('\n')
            payloads = [line[5:].strip() for line in lines if line.startswith('data:')]
            if not payloads or payloads[-1] != '[DONE]':
                raise ValueError('incomplete stream')
            objects = [parse(line) for line in payloads[:-1]]
        else:
            objects = [parse(data)]
        usages = [obj['usage'] for obj in objects if isinstance(obj, dict) and obj.get('usage') is not None]
        if len(usages) != 1 or not isinstance(usages[0], dict):
            raise ValueError('one final usage object required')
        usage = usages[0]
        values = {key: usage.get(key) for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
        if any(type(x) is not int or x < 0 for x in values.values()):
            raise ValueError('invalid counters')
        if values['prompt_tokens'] + values['completion_tokens'] != values['total_tokens']:
            raise ValueError('inconsistent counters')
        for field, details, key, upper in (
                ('reasoning_tokens', 'completion_tokens_details', 'reasoning_tokens', 'completion_tokens'),
                ('cached_tokens', 'prompt_tokens_details', 'cached_tokens', 'prompt_tokens')):
            detail = usage.get(details) or {}
            value = detail.get(key)
            if value is not None and (type(value) is not int or not 0 <= value <= values[upper]):
                raise ValueError('invalid detailed counter')
            values[field] = value
        return {'status': 'COMPLETE', **values}
    except (ValueError, TypeError, AttributeError, UnicodeError):
        return {'status': 'MISSING_OR_INVALID', 'prompt_tokens': None,
                'completion_tokens': None, 'total_tokens': None,
                'reasoning_tokens': None, 'cached_tokens': None}


class Rejected(ValueError):
    pass


class Ledger:
    def __init__(self, model, *, limit=50, seconds=300, clock=time.monotonic):
        if (not isinstance(model, str) or not model or type(limit) is not int
                or not 1 <= limit <= 50 or type(seconds) not in (int, float)
                or not math.isfinite(seconds) or not 0 < seconds <= 300):
            raise ValueError('bounded single-task ledger required')
        self.model, self.limit, self.seconds, self.clock = model, limit, seconds, clock
        self.lock = threading.Lock()
        self.started = self.deadline = None
        self.rows, self.denied = [], []
        self.closed = False

    def start(self):
        with self.lock:
            if self.started is not None or self.closed:
                raise ValueError('ledger cannot be reset or reused')
            self.started = self.clock(); self.deadline = self.started + self.seconds

    def remaining(self):
        if self.started is None or self.closed:
            raise Rejected('task not active')
        left = self.deadline - self.clock()
        if left <= 0:
            raise Rejected('task work deadline exhausted')
        return left

    def admit(self, data):
        with self.lock:
            try:
                self.remaining()
                if len(self.rows) >= self.limit:
                    raise Rejected('total model request allowance exhausted')
                value = parse(data)
                if not isinstance(value, dict) or value.get('model') != self.model:
                    raise Rejected('unexpected model')
                if value.get('temperature') != 0.2 or value.get('top_p') != 0.95:
                    raise Rejected('sampling mismatch')
                maximum = value.get('max_tokens', value.get('max_completion_tokens'))
                if maximum != 16384 or ('max_tokens' in value and 'max_completion_tokens' in value):
                    raise Rejected('output allowance mismatch')
                if value.get('n', 1) != 1 or value.get('chat_template_kwargs') != {'enable_thinking': True}:
                    raise Rejected('generation multiplicity or thinking bridge mismatch')
                if value.get('stream', False) not in (True, False):
                    raise Rejected('invalid stream flag')
                if value.get('stream'):
                    value['stream_options'] = {'include_usage': True}
                forwarded = json.dumps(value, separators=(',', ':'), allow_nan=False).encode()
                row = {'request': len(self.rows) + 1, 'request_sha256': hashlib.sha256(data).hexdigest(),
                       'forwarded_sha256': hashlib.sha256(forwarded).hexdigest(),
                       'streaming': bool(value.get('stream')), 'http_status': None,
                       'finished': False, 'elapsed_seconds': None, 'usage': None,
                       'sampling': {k: value.get(k) for k in ('temperature', 'top_p', 'max_tokens',
                                    'max_completion_tokens', 'seed', 'chat_template_kwargs')}}
                self.rows.append(row)
                return row['request'], forwarded
            except ValueError as error:
                # Fixed rejection labels only; no model input is logged.
                reason = str(error) if isinstance(error, Rejected) else 'invalid request JSON'
                self.denied.append({'reason': reason, 'elapsed_seconds': None if self.started is None
                                    else self.clock() - self.started})
                raise Rejected(reason) from None

    def finish(self, number, status, data, error=None):
        with self.lock:
            row = self.rows[number - 1]
            if row['finished']:
                raise ValueError('duplicate response accounting')
            row.update(finished=True, http_status=status, response_sha256=hashlib.sha256(data).hexdigest(),
                       elapsed_seconds=self.clock() - self.started, transport_error=error,
                       usage=token_usage(data, row['streaming']))

    def close(self):
        with self.lock:
            self.closed = True

    def report(self):
        with self.lock:
            rows = copy.deepcopy(self.rows)
            complete = bool(rows) and all(r['finished'] and not r.get('transport_error')
                and r['usage']['status'] == 'COMPLETE' for r in rows)
            totals = {}
            for key in ('prompt_tokens', 'completion_tokens', 'total_tokens', 'reasoning_tokens', 'cached_tokens'):
                values = [r['usage'].get(key) if r['usage'] else None for r in rows]
                totals[key] = sum(values) if complete and all(v is not None for v in values) else None
            return {'schema_version': 1, 'admitted_requests': len(rows), 'rejected_requests': len(self.denied),
                    'request_limit': self.limit, 'session_seconds': self.seconds,
                    'token_accounting': 'COMPLETE' if complete else 'INCOMPLETE', 'totals': totals,
                    'requests': rows, 'rejections': copy.deepcopy(self.denied),
                    'closed': self.closed, 'boundary': 'ALL HTTP attempts at this gateway; OS bypass protection required',
                    'reasoning_tokens_are_subset_of_completion': True}


class Gateway(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True


@contextlib.contextmanager
def gateway(ledger, upstream_port):
    if type(upstream_port) is not int or not 1 <= upstream_port <= 65535:
        raise ValueError('loopback upstream port required')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reject(self, message):
            # 400 is terminal in the retained client; 429 would invite retries.
            body = json.dumps({'error': {'type': 'BacktraceBudgetError', 'message': message}}).encode()
            self.send_response(400); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_POST(self):
            self.connection.settimeout(2)
            number = None; response_bytes = bytearray(); status = None; error = None
            connection = None
            try:
                if self.path != '/v1/chat/completions' or self.headers.get('Transfer-Encoding'):
                    raise Rejected('only bounded chat requests allowed')
                lengths = self.headers.get_all('Content-Length', [])
                if len(lengths) != 1 or not lengths[0].isdigit() or not 0 < int(lengths[0]) <= BODY_LIMIT:
                    raise Rejected('bounded request length required')
                data = self.rfile.read(int(lengths[0]))
                if len(data) != int(lengths[0]):
                    raise Rejected('incomplete request')
                number, data = ledger.admit(data)
                connection = http.client.HTTPConnection('127.0.0.1', upstream_port, timeout=ledger.remaining())
                connection.request('POST', self.path, body=data, headers={'Content-Type': 'application/json',
                                    'Authorization': 'Bearer EMPTY', 'Accept-Encoding': 'identity'})
                response = connection.getresponse(); status = response.status
                self.send_response(status)
                self.send_header('Content-Type', response.getheader('Content-Type', 'application/json'))
                self.send_header('Connection', 'close'); self.end_headers()
                while True:
                    left = ledger.remaining()
                    if connection.sock is not None:
                        connection.sock.settimeout(left)
                    chunk = response.read1(65536)
                    if not chunk:
                        break
                    response_bytes.extend(chunk)
                    if len(response_bytes) > RESPONSE_LIMIT:
                        raise Rejected('response size bound exceeded')
                    self.connection.settimeout(min(2, ledger.remaining()))
                    self.wfile.write(chunk); self.wfile.flush()
            except Rejected as exc:
                error = 'BUDGET_OR_PROTOCOL'
                if number is None:
                    with contextlib.suppress(OSError): self.reject(str(exc))
            except Exception as exc:
                error = type(exc).__name__
            finally:
                if connection is not None:
                    connection.close()
                if number is not None:
                    ledger.finish(number, status, bytes(response_bytes), error)
                self.close_connection = True

    server = Gateway(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield server.server_port
    finally:
        ledger.close()
        server.shutdown(); server.server_close(); thread.join(timeout=2)
        if thread.is_alive():
            raise RuntimeError('accounting gateway did not stop')
