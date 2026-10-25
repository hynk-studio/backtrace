import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from tools.research_lifecycle import Journal,cleanup,watch
from tools.research_serving_delivery import bundle,FILES
from tools.research_serving_install import expected,WHEELS_SHA256
from tools.research_serving import MODEL_MANIFEST_SHA256,readiness
from tools.research_split import credentials
from tools.research_split_server import MODEL_PATH
from tools.a100_delivery import manifest,ROOT


class ServingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def journal(self,seconds=5,stale=.2):
        return Journal.create(self.root,'a'*40,'123',seconds=seconds,stale_seconds=stale)

    def test_serving_payload_excludes_task_compiler_and_client_key(self):
        credentials(self.root/'tls');raw=bundle(self.root/'payload',self.root/'tls')
        names={r['path'] for r in json.loads(raw)['files']}
        self.assertEqual(names,set(FILES)|{'transport/server.key','transport/server.crt','transport/client.crt'})
        self.assertNotIn('tools/research_official.py',names)
        self.assertFalse(any('task' in n or 'evaluator' in n or n.endswith('client.key') for n in names))
        self.assertNotIn('tests/research_serving_fixture.py',names)

    def test_fixture_needs_explicit_separate_bundle(self):
        credentials(self.root/'tls');raw=bundle(self.root/'payload',self.root/'tls',authored_cpu=True)
        self.assertIn('tests/research_serving_fixture.py',{r['path'] for r in json.loads(raw)['files']})

    def test_frozen_model_and_complete_serving_closure(self):
        from tools.research_official import MODEL_PATH as frozen_path
        self.assertEqual(MODEL_PATH,frozen_path)
        self.assertEqual(hashlib.sha256(manifest('model')).hexdigest(),MODEL_MANIFEST_SHA256)
        self.assertEqual(hashlib.sha256(manifest('wheels')).hexdigest(),WHEELS_SHA256)
        self.assertEqual(len(expected(ROOT/'docs/linux-wheel-manifest.json')),246)
        changed=self.root/'changed.json';changed.write_text('[]')
        with self.assertRaises(ValueError):expected(changed)

    def test_namespaces_are_new_and_claims_create_only(self):
        first,second=self.journal(),self.journal()
        self.assertNotEqual(first.root,second.root)
        with self.assertRaises(FileExistsError):first.write('claim',first.claim())
        self.assertEqual(first.claim()['authorization'],'NONE')
        with self.assertRaises(ValueError):first.require_watcher()

    def test_watcher_must_bind_same_namespace(self):
        journal=self.journal()
        journal.write('watcher',{'claim_sha256':'0'*64,'at':time.time()})
        with self.assertRaises(ValueError):journal.require_watcher()

    def test_stale_watcher_cannot_allow_create(self):
        journal=self.journal()
        journal.write('watcher',{'claim_sha256':journal.binding(),'at':time.time()-1})
        with self.assertRaises(ValueError):journal.require_watcher()

    def test_no_query_error_counts_as_absence(self):
        class Resource:
            def observe(self):raise OSError('unavailable')
        result=cleanup(Resource(),seconds=.12)
        self.assertEqual(result['status'],'FAIL');self.assertEqual(result['absence_reads'],0)

    def test_lost_delete_ack_requires_two_real_absence_reads(self):
        class Resource:
            present=True
            def observe(self):return 'owned' if self.present else None
            def delete(self,identity):self.present=False;raise OSError('lost ack')
        result=cleanup(Resource(),seconds=1)
        self.assertEqual(result['status'],'PASS');self.assertEqual(result['absence_reads'],2)

    def test_false_delete_ack_does_not_prove_cleanup(self):
        class Resource:
            def observe(self):return 'owned'
            def delete(self,identity):pass
        result=cleanup(Resource(),seconds=.12)
        self.assertEqual(result['status'],'FAIL')

    def test_owner_loss_cleans_without_owner_finalizer(self):
        journal=self.journal();deleted=[]
        class Resource:
            def observe(self):return None if deleted else 'owned'
            def delete(self,identity):deleted.append(identity)
        result=watch(journal,Resource(),interval=.01)
        self.assertEqual(result['reason'],'OWNER_LOST');self.assertEqual(result['status'],'PASS')
        self.assertEqual(deleted,['owned'])

    def test_state_read_failure_still_reclaims_bound_resource(self):
        journal=self.journal();original=journal.read
        def read(name):
            if name=='heartbeat':raise OSError('state unavailable')
            return original(name)
        class Resource:
            def observe(self):return None
        with patch.object(journal,'read',read):result=watch(journal,Resource(),interval=.01)
        self.assertEqual(result['reason'],'STATE_UNAVAILABLE');self.assertEqual(result['absence_reads'],2)

    def test_authored_readiness_never_qualifies_model(self):
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                data=b'{"status":"AUTHORED_CPU","model_execution":false}'
                self.send_response(200);self.send_header('Content-Length',str(len(data)))
                self.end_headers();self.wfile.write(data)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever);thread.start()
        try:
            self.assertTrue(readiness(server.server_port,authored=True))
            self.assertIsNone(readiness(server.server_port,authored=False))
        finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
