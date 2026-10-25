import contextlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import ssl
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest

from tools.research_meter import Ledger, gateway
from tools.research_split import Endpoint, credentials, fingerprint, inference_proxy
from tests.test_research_meter import request, response
from tools.research_split_sequence import sequence
from tools.research_split_server import observed_configuration, MODEL_PATH
from tools.research_runner import recover_submission
from tools import research_comparison as comparison


@contextlib.contextmanager
def authored(mode='ordinary'):
    rows = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length'])); rows.append(json.loads(body))
            if mode == 'stall':
                self.connection.settimeout(4)
                self.connection.recv(1)
                return
            status = 500 if mode == 'retry' and len(rows)==1 else 200
            data = b'{"error":"authored"}' if status==500 else response()
            if rows[-1].get('stream'):
                data = b'data: '+data+b'\n\ndata: [DONE]\n\n'
            self.send_response(status); self.send_header('Content-Length', str(len(data)))
            self.send_header('Content-Type', 'text/event-stream' if rows[-1].get('stream') else 'application/json')
            self.end_headers(); self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever); thread.start()
    try: yield server.server_port, rows
    finally: server.shutdown(); server.server_close(); thread.join(timeout=2)


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.material = self.root/'tls'; self.pins = credentials(self.material)

    def tearDown(self): self.temp.cleanup()

    def endpoint(self, port, material=None):
        return Endpoint('127.0.0.1', port, material or self.material, self.pins['server_sha256'])

    def call(self, port, data):
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        try:
            connection.request('POST', '/v1/chat/completions', body=data)
            reply = connection.getresponse(); return reply.status, reply.read()
        finally: connection.close()

    def test_remote_stream_and_json_share_exact_fifty_attempts(self):
        ledger = Ledger('frozen-model'); ledger.start()
        with authored() as (origin, rows), inference_proxy(self.material, origin) as (port, state):
            with gateway(ledger, upstream=self.endpoint(port)) as gate:
                for i in range(50): self.assertEqual(self.call(gate, request(stream=bool(i%2)))[0],200)
                self.assertEqual(self.call(gate, request())[0],400)
            self.assertEqual(state['requests'],50)
            self.assertEqual(len(rows),50)
        report=ledger.report()
        self.assertEqual(report['totals']['total_tokens'],900)
        self.assertEqual(report['token_accounting'],'COMPLETE')
        self.assertEqual(state['active'],0)

    def test_retry_is_charged_and_missing_usage_remains_unknown(self):
        ledger=Ledger('frozen-model'); ledger.start()
        with authored('retry') as (origin, rows), inference_proxy(self.material,origin) as (port,state):
            with gateway(ledger, upstream=self.endpoint(port)) as gate:
                self.assertEqual(self.call(gate,request())[0],500)
                self.assertEqual(self.call(gate,request())[0],200)
        report=ledger.report()
        self.assertEqual(report['admitted_requests'],2)
        self.assertEqual(report['token_accounting'],'INCOMPLETE')
        self.assertIsNone(report['totals']['total_tokens'])

    def test_client_disconnect_cancels_stalled_remote_upstream(self):
        ledger=Ledger('frozen-model', seconds=.4); ledger.start()
        began=time.monotonic()
        with authored('stall') as (origin, rows), inference_proxy(self.material,origin) as (port,state):
            with gateway(ledger, upstream=self.endpoint(port)) as gate:
                with self.assertRaises(http.client.RemoteDisconnected): self.call(gate,request())
            deadline=time.monotonic()+2
            while state['active'] and time.monotonic()<deadline: time.sleep(.02)
            self.assertEqual(state['active'],0)
        self.assertLess(time.monotonic()-began,3)
        self.assertEqual(ledger.report()['admitted_requests'],1)
        self.assertEqual(ledger.report()['token_accounting'],'INCOMPLETE')

    def test_wrong_client_no_client_and_wrong_server_fail_before_inference(self):
        other=self.root/'other'; credentials(other)
        with authored() as (origin,rows), inference_proxy(self.material,origin) as (port,state):
            for key in (None,other):
                ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); ctx.check_hostname=False
                ctx.load_verify_locations(self.material/'server.crt')
                if key: ctx.load_cert_chain(key/'client.crt', key/'client.key')
                conn=http.client.HTTPSConnection('127.0.0.1',port,context=ctx,timeout=2)
                with self.assertRaises((ssl.SSLError,ConnectionError)):
                    conn.request('POST','/v1/chat/completions',body=request(),headers={'X-Backtrace-Seconds':'1'})
                    conn.getresponse().read()
                conn.close()
            bad=Endpoint('127.0.0.1',port,other,fingerprint(other/'server.crt'))
            conn=bad.connection(2)
            with self.assertRaises(ssl.SSLError): conn.connect()
            conn.close(); self.assertEqual(rows,[])

    def test_cert_pin_private_modes_and_mutually_exclusive_routes(self):
        with self.assertRaises(ValueError): Endpoint('127.0.0.1',1,self.material,'0'*64)
        (self.material/'client.key').chmod(0o644)
        with self.assertRaises(ValueError): self.endpoint(1).context()
        (self.material/'client.key').chmod(0o600)
        with self.assertRaises(ValueError), gateway(Ledger('frozen-model'),1,upstream=self.endpoint(1)): pass

    def test_remote_rejects_arbitrary_paths_and_unbounded_time(self):
        with authored() as (origin,rows), inference_proxy(self.material,origin) as (port,state):
            for path,seconds in (('/shell','1'),('/v1/chat/completions','nan'),('/v1/chat/completions','301')):
                conn=self.endpoint(port).connection(2)
                conn.request('POST',path,body=request(),headers={'X-Backtrace-Seconds':seconds})
                reply=conn.getresponse(); self.assertEqual(reply.status,400); reply.read(); conn.close()
            self.assertEqual(rows,[])

    def test_service_lifetime_closes_an_idle_listener(self):
        with authored() as (origin,rows), inference_proxy(self.material,origin,lifetime=.15) as (port,state):
            time.sleep(.25)
        with self.assertRaises(OSError): socket.create_connection(('127.0.0.1',port),timeout=.2)

    def test_shutdown_interrupts_an_authenticated_incomplete_body(self):
        with authored() as (origin,rows):
            began=time.monotonic()
            with inference_proxy(self.material,origin,lifetime=.4) as (port,state):
                connection=self.endpoint(port).connection(2);connection.connect()
                connection.sock.sendall(b'POST /v1/chat/completions HTTP/1.1\r\nHost: fixture\r\n'
                    b'Content-Length: 100\r\nX-Backtrace-Seconds: 300\r\n\r\nx')
                time.sleep(.1)
            connection.close()
            self.assertLess(time.monotonic()-began,2)
            self.assertEqual(rows,[])


class SequenceTests(unittest.TestCase):
    def test_exact_order_denominator_and_remaining_time_reserve(self):
        now=[0];calls=[]
        def execute(identifier,arm,seconds):
            calls.append((identifier,arm,seconds));now[0]+=330;return {'status':'PASS'}
        result=sequence(execute,deadline=10800,clock=lambda:now[0])
        self.assertEqual(len(calls),18)
        self.assertEqual(len({(a,b) for a,b,_ in calls}),18)
        self.assertTrue(all(s==330 for _,_,s in calls))
        calls.clear();now[0]=0
        result=sequence(execute,deadline=1320,clock=lambda:now[0])
        self.assertEqual(len(calls),2)
        self.assertEqual([r['status'] for r in result['slots']].count('NOT_RUN'),16)
        self.assertFalse(result['all_slots_attempted'])

    def test_infrastructure_failure_retains_all_remaining_slots(self):
        def fail(*args):raise ConnectionError('fixture disconnected')
        result=sequence(fail,deadline=10800,clock=lambda:0)
        self.assertEqual(result['slots'][0]['status'],'INFRASTRUCTURE_FAILURE')
        self.assertEqual(len(result['slots']),18)
        self.assertEqual([r['status'] for r in result['slots']].count('NOT_RUN'),17)

    def test_initialized_cache_contract_rejects_enabled_or_missing(self):
        config=SimpleNamespace(model_config=SimpleNamespace(model=MODEL_PATH,dtype='bfloat16',max_model_len=32768),
            parallel_config=SimpleNamespace(tensor_parallel_size=1,disable_custom_all_reduce=True),
            cache_config=SimpleNamespace(enable_prefix_caching=False))
        self.assertIs(observed_configuration(config)['enable_prefix_caching'],False)
        for value in (True,None,0):
            config.cache_config.enable_prefix_caching=value
            with self.assertRaises(ValueError):observed_configuration(config)


class SubmissionRecoveryTests(unittest.TestCase):
    def test_api_error_empty_return_recovers_exact_acknowledged_submission(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'checkpoint.json';patch='diff --git a/marker b/marker\n+fixture\n'
            saved={'source':'ORIGINAL_SUBMIT_PATCH','instance_id':'fixture_1','arm':'R0',
                'candidate_sha256':'a'*64,'patch':patch,'bytes':len(patch.encode()),
                'sha256':comparison.digest(patch.encode())}
            path.write_bytes(comparison.encoded(saved))
            result,receipt=recover_submission('',patch,path,'fixture_1','R0','a'*64)
            self.assertEqual(result,patch)
            self.assertEqual(receipt['source'],'ORIGINAL_SUBMIT_CHECKPOINT')
            self.assertEqual(receipt['after_deadline_workspace_commands'],0)
            _,receipt=recover_submission(patch,patch,path,'fixture_1','R0','a'*64)
            self.assertEqual(receipt['source'],'OFFICIAL_RETURN')
            for key,value in (('arm','R1'),('candidate_sha256','b'*64),('sha256','0'*64),('patch',patch+'extra')):
                path.write_bytes(comparison.encoded({**saved,key:value}))
                with self.assertRaises(ValueError):recover_submission('',patch,path,'fixture_1','R0','a'*64)


if __name__=='__main__': unittest.main()
