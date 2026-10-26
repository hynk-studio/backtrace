"""Wire, accounting and durable-recovery controls; native isolation has a separate probe."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import exact_teacher as exact
from tools import small_model_runner as run
from tools import small_model_readiness as ready


class Tokenizer:
    def __len__(self):return 1000
    def decode(self,ids,**kwargs):
        self.kwargs=kwargs
        return ''.join({1:'<eos>',106:'<turn|>',50:'<|tool_response>',10:'{}',11:'```json\n{}\n```',
                        12:'{"x":1,"x":2}',13:'<|channel>thought',14:'NaN'}[t] for t in ids)


def request(index=0):
    return {'model':'E2B','arm':'B0' if index%2==0 else 'B1','id':str(index),
            'messages':[],'input_tokens':5,'input_ids_sha256':'0'*64}


def frame(req,ids=None):
    ids=[10,106] if ids is None else ids
    return {'id':req['id'],'input_tokens':5,'input_ids_sha256':'0'*64,'output_ids':ids,
            'raw_text':Tokenizer().decode(ids),'elapsed_seconds':.01}


class WireTests(unittest.TestCase):
    def test_raw_ids_and_text_are_retained_and_only_one_terminal_removed(self):
        token=Tokenizer();result=run.response_record(frame(request()),request(),token,4096)
        self.assertEqual(result['raw_text'],'{}<turn|>')
        self.assertEqual(result['raw_output_ids'],[10,106]);self.assertEqual(result['answer_text'],'{}')
        self.assertEqual(result['status'],'OK');self.assertFalse(token.kwargs['skip_special_tokens'])
        self.assertEqual(run.response_record(frame(request(),[10,106,106]),request(),token,4096)['status'],'INVALID_OUTPUT')

    def test_tool_thought_fence_duplicate_json_and_nonfinite_are_invalid(self):
        for ids in ([10,50],[10,50,106],[13,10,106],[11,106],[12,106],[14,106]):
            with self.subTest(ids=ids):
                result=run.response_record(frame(request(),ids),request(),Tokenizer(),4096)
                self.assertEqual(result['status'],'INVALID_OUTPUT');self.assertEqual(result['raw_output_ids'],ids)

    def test_limit_or_unterminated_output_is_not_repaired(self):
        self.assertEqual(run.response_record(frame(request(),[10]),request(),Tokenizer(),1)['finish_reason'],'LENGTH_LIMIT')
        self.assertEqual(run.response_record(frame(request(),[10]),request(),Tokenizer(),4096)['finish_reason'],'NO_TERMINAL')

    def test_identity_count_hash_text_types_and_duration_must_match(self):
        changes=[{'id':'wrong'},{'input_tokens':6},{'input_ids_sha256':'bad'},{'raw_text':'{}'},
                 {'output_ids':[]},{'output_ids':[True]},{'output_ids':[-1]},{'output_ids':[1000]},
                 {'elapsed_seconds':float('nan')},{'elapsed_seconds':-1},{'elapsed_seconds':True}]
        for change in changes:
            f=frame(request());f.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):run.response_record(f,request(),Tokenizer(),4096)


class LocalTests(unittest.TestCase):
    def setUp(self):
        (exact.ROOT/'.local').mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=exact.ROOT/'.local');self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()

    def test_real_pipe_timeout_and_oversize_are_bounded(self):
        for script,error in [('import time; time.sleep(30)',TimeoutError),
                             ('import sys;sys.stdout.write("x"*1048577);sys.stdout.flush()',ValueError),
                             ('print("{}\\n{}")',ValueError),('print("{bad}")',ValueError)]:
            channel=run.Channel([sys.executable,'-I','-c',script],self.root/(str(time.monotonic_ns())+'.log'))
            try:
                with self.assertRaises(error):channel.read(time.monotonic()+.3)
                self.assertLessEqual(len(channel.partial),run.MAX_FRAME+1)
            finally:channel.close()

    def test_regular_reader_rejects_symlinks_and_hardlinks(self):
        path=self.root/'input';path.write_text('x')
        link=self.root/'link';link.symlink_to(path)
        with self.assertRaises(OSError):run.regular(link)
        os.link(path,self.root/'hard')
        with self.assertRaises(ValueError):run.regular(path)

    def test_full_pretrained_hash_and_configuration_required(self):
        model=self.root/'model';model.mkdir()
        config=b'{"fixture":true}';weights=b'authored weight verifier fixture'
        for name in ('config.json','generation_config.json'):(model/name).write_bytes(config)
        (model/'model.safetensors').write_bytes(weights)
        spec={'models':{'E2B':{'revision':'f'*40,'files':{n:{'bytes':len(config),'sha256':exact.sha(config)}
              for n in ('config.json','generation_config.json')},
              'weights_metadata_only':[{'bytes':len(weights),'lfs':{'oid':exact.sha(weights)}}]}}}
        with patch.object(ready,'lock',return_value=spec):
            self.assertEqual(run.verify_pretrained_directory('E2B',model)['sha256'],exact.sha(weights))
            (model/'model.safetensors').write_bytes(b'x'*len(weights))
            with self.assertRaises(ValueError):run.verify_pretrained_directory('E2B',model)
            (model/'model.safetensors').write_bytes(weights)
            (model/'config.json').write_bytes(b'{}')
            with self.assertRaises(ValueError):run.verify_pretrained_directory('E2B',model)
            (model/'config.json').write_bytes(config)
            (model/'labels.json').write_text('must not mount')
            with self.assertRaises(ValueError):run.verify_pretrained_directory('E2B',model)

    def test_asset_snapshot_excludes_private_siblings_and_preserves_source_permissions(self):
        model=self.root/'model';model.mkdir(mode=0o700)
        tokenizer=self.root/'tokenizer';tokenizer.mkdir(mode=0o700)
        for directory,names in [(model,{'config.json','generation_config.json','model.safetensors'}),(tokenizer,ready.FILES)]:
            for name in names:
                p=directory/name;p.write_bytes(b'fixture');p.chmod(0o600)
            (directory/'evaluator-secret').write_bytes(b'must not copy')
        job=self.root/'job';job.write_text('{}');job.chmod(0o600)
        script=self.root/'worker';script.write_text('pass')
        stage=run.snapshot_assets(model,tokenizer,job,script)
        try:
            self.assertEqual({p.name for p in stage.iterdir()},{'model','tokenizer','job.json','worker.py'})
            self.assertEqual({p.name for p in (stage/'model').iterdir()},{'config.json','generation_config.json','model.safetensors'})
            self.assertEqual((model/'config.json').stat().st_mode&0o777,0o600)
            self.assertEqual(model.stat().st_mode&0o777,0o700)
            self.assertEqual((stage/'model/config.json').stat().st_mode&0o777,0o444)
            self.assertFalse(any(p.name=='evaluator-secret' for p in stage.rglob('*')))
        finally:run.shutil.rmtree(stage)
        (model/'config.json').unlink();(model/'config.json').symlink_to(job)
        with self.assertRaises(ValueError):run.snapshot_assets(model,tokenizer,job,script)

    def test_runtime_private_parent_is_rejected_without_chmod(self):
        with tempfile.TemporaryDirectory(prefix='backtrace-runtime-test-') as name:
            parent=Path(name);parent.chmod(0o700)
            runtime=parent/'runtime';runtime.mkdir(mode=0o755)
            with self.assertRaisesRegex(ValueError,'not traversable'):
                run.require_worker_traversal(runtime)
            self.assertEqual(parent.stat().st_mode&0o777,0o700)
            parent.chmod(0o755)
            run.require_worker_traversal(runtime)

    def test_prepared_scope_matches_published_inputs_and_rejects_tampering(self):
        # Full prompt byte reconstruction is separately covered by readiness;
        # exercise every actual smoke field and its fixed paired schedule here.
        packets=self.root/'packets';ready.rebuild_packets(packets)
        rows,_=ready.read_packets(packets)
        cases=[{'model':m,'packet':p,'id':r['id'],'input_tokens':5,'overflow':False,
                'token_ids_sha256':'0'*64,'rendered_sha256':'1'*64}
                for m in ready.MODELS for p,rr in rows.items() for r in rr]
        report={'status':'PASS_TOKENIZATION_ONLY','overflow':0,'source_hashes':ready.source_hashes(),
                'baseline_manifest_sha256':ready.lock()['baseline_manifest_sha256'],
                'generation':ready.lock()['generation'],'cases':cases,'assignments':len(cases),
                'summaries':{m:{p:dict(ready.distribution([5]*len(rr)),overflow=0) for p,rr in rows.items()} for m in ready.MODELS}}
        tokenfile=self.root/'tokens';tokenfile.write_bytes(exact.canonical(report))
        scope=self.root/'scope';original=ready.prepare_scope(packets,tokenfile,scope)
        plan,schedule,_=run.load_scope(scope,packets,tokenfile)
        self.assertEqual(len(schedule),36)
        self.assertEqual([(s['model'],s['arm']) for s in schedule[:4]],[('E2B','B0'),('E2B','B1')]*2)
        self.assertEqual(schedule[0]['id'],schedule[1]['id'])
        for change in [lambda p:p.update(total_requests=35),lambda p:p['selection'].pop(),
                       lambda p:p['models']['E2B'].update(revision='0'*40),
                       lambda p:p['input_tokens_per_model'].update(E2B=1),
                       lambda p:p['generation'].update(max_new_tokens=1)]:
            p=deepcopy(original);change(p);(scope/'plan.json').write_bytes(exact.canonical(p))
            with self.assertRaises(ValueError):run.load_scope(scope,packets,tokenfile)

    def collector(self,channel,**kwargs):
        return run.collect([request(i) for i in range(4)],self.root/'run',lambda *a:channel,
            {'E2B':Tokenizer()},mode='random_fixture',max_new_tokens=2,total_seconds=2,
            startup_seconds=1,request_seconds=1,**kwargs)

    def test_partial_failure_retains_denominator_and_raw_prior_response(self):
        channel=FakeChannel(fail_at=1)
        result=self.collector(channel)
        self.assertEqual(result['coverage'],{'OK':1,'TIMEOUT':1,'NOT_RUN':2})
        self.assertTrue(channel.closed);self.assertEqual(channel.calls,2)
        self.assertTrue((self.root/'run/wire-0000.json').is_file())
        recovered=run.recover(self.root/'run')
        self.assertEqual(recovered['coverage'],result['coverage'])

    def test_wrong_handshake_stops_before_any_request(self):
        channel=FakeChannel();channel.mode='scripted_control'
        result=self.collector(channel)
        self.assertEqual(result['coverage'],{'NOT_RUN':4});self.assertEqual(channel.calls,0)
        self.assertEqual(result['status'],'INCOMPLETE')

    def test_coordinator_exception_is_recorded_incomplete(self):
        channel=FakeChannel(fail_at=0,error=RuntimeError)
        with self.assertRaises(RuntimeError):self.collector(channel)
        result=json.loads((self.root/'run/collection.json').read_bytes())
        self.assertEqual(result['status'],'INCOMPLETE');self.assertTrue(channel.closed)
        recovered=run.recover(self.root/'run')
        self.assertEqual(recovered['coverage'],{'INTERRUPTED':1,'NOT_RUN':3})

    def test_nonzero_worker_exit_never_reports_completed(self):
        channel=FakeChannel();channel.exit=23
        result=self.collector(channel)
        self.assertEqual(result['coverage'],{'OK':4});self.assertEqual(result['status'],'INCOMPLETE')

    def test_recovery_retains_truncated_tail_and_rejects_duplicate_events(self):
        self.collector(FakeChannel(fail_at=1))
        ledger=self.root/'run/ledger.jsonl'
        with ledger.open('ab') as f:f.write(b'{"incomplete":')
        self.assertTrue(run.recover(self.root/'run')['partial_final_ledger_line'])
        (self.root/'run/recovery.json').unlink()
        lines=ledger.read_bytes().splitlines(keepends=True)
        ledger.write_bytes(lines[0]+lines[0])
        with self.assertRaises(ValueError):run.recover(self.root/'run')

    def test_fixture_injection_and_unbounded_limits_are_rejected(self):
        with self.assertRaises(ValueError):self.collector(FakeChannel(),fixture_ids={})
        self.assertFalse((self.root/'run').exists())

    def test_startup_counts_against_total_deadline(self):
        channel=FakeChannel();channel.delay=.15
        result=run.collect([request(i) for i in range(2)],self.root/'run',lambda *a:channel,{'E2B':Tokenizer()},
            mode='random_fixture',max_new_tokens=2,total_seconds=.1,startup_seconds=.1,request_seconds=.1)
        self.assertEqual(result['status'],'INCOMPLETE');self.assertEqual(channel.calls,1)
        self.assertLessEqual(channel.last_deadline,channel.read_started+.11)


class FakeChannel:
    def __init__(self,fail_at=None,error=TimeoutError):
        self.fail_at=fail_at;self.error=error;self.calls=0;self.closed=False;self.partial=b''
        self.mode='random_fixture';self.exit=0;self.delay=0
    def read(self,deadline):
        self.read_started=time.monotonic();time.sleep(self.delay)
        return {'ready':True,'mode':self.mode,'uid':65532,'caps':0,'no_new_privs':'1',
                'pid_namespace':'fixture-pid','net_namespace':'fixture-net'}
    def exchange(self,req,deadline):
        self.last_deadline=deadline;index=self.calls;self.calls+=1;self.partial=b''
        if time.monotonic()>=deadline or index==self.fail_at:raise self.error('fixture failure')
        result=frame(req);self.partial=exact.canonical(result);return result
    def close(self):self.closed=True;return self.exit


if __name__=='__main__':unittest.main()
