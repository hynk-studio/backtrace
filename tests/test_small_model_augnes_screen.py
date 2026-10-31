import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from tools import small_model_augnes_screen as screen
from tools import small_model_pretrained as entry


class ScreeningTests(unittest.TestCase):
    def test_twenty_inputs_exclude_rubric_and_outcomes_and_refuse_overflow(self):
        encoded={'overflow':False,'input_tokens':100,'token_ids_sha256':'a'*64}
        with patch.object(screen.ready,'encode',return_value=encoded):
            rows=screen.schedule(Mock())
        self.assertEqual(len(rows),20);self.assertEqual(len({r['id'] for r in rows}),20)
        packet=json.loads(screen.PACKET.read_bytes())
        for case,row in zip(packet['cases'],rows):
            self.assertEqual(row['arm'],'B1')
            payload=json.loads(row['messages'][1]['content'])
            self.assertEqual(payload['facts'],case['facts'])
            self.assertEqual(set(payload),{'id','cutoff','goal','facts','prior_claims','constraints',
                             'allowed_checks','question','output_contract'})
            self.assertNotIn('rubric',payload);self.assertNotIn('source_issue_body_sha256',payload)
        with patch.object(screen.ready,'encode',return_value=dict(encoded,overflow=True)):
            with self.assertRaises(ValueError):screen.schedule(Mock())

    def test_untrained_collector_uses_separate_job_and_preserves_failed_records(self):
        import sys,types
        module=types.ModuleType('transformers');module.AutoTokenizer=Mock()
        with tempfile.TemporaryDirectory(dir=screen.ROOT/'.local') as td:
            root=Path(td);(root/'.local').mkdir();spec=root/'spec.json'
            spec.write_text(json.dumps({'prefix':['fixture'],'gpu_uuid':'fixture'}))
            with patch.object(screen,'ROOT',root),patch.dict(sys.modules,{'transformers':module}),\
                    patch.object(screen,'assigned_schedule',return_value=[{'model':'E2B','arm':'B1','id':'fixture'}]),\
                    patch.object(screen.runner,'collect',return_value={'status':'INCOMPLETE'}) as collect,\
                    patch.object(screen.container,'ContainerChannel') as channel:
                self.assertEqual(screen.collect(spec,root)['status'],'INCOMPLETE')
                args,kw=collect.call_args;factory=args[2]
                self.assertFalse(factory.training_requested)
                factory('E2B',root)
                self.assertIn('E2B-screening',channel.call_args.args[0][-1])
                self.assertEqual(kw['max_new_tokens'],768)
                self.assertEqual(kw['total_seconds'],900)
                source=root/'.local/augnes-screening-collection';source.mkdir()
                (source/'collection.json').write_text('{"status":"INCOMPLETE"}')
                self.assertEqual(screen.preserve(root)['files'],1)
                self.assertEqual((root/'augnes-screening/collection.json').read_bytes(),
                                 (source/'collection.json').read_bytes())

    def test_completion_keeps_exact_inputs_and_does_not_retry_invalid_finished_answer(self):
        encoded={'overflow':False,'input_tokens':100,'token_ids_sha256':'a'*64}
        with patch.object(screen.ready,'encode',return_value=encoded):
            original=screen.schedule(Mock());selected=screen.assigned_schedule(Mock())
        self.assertEqual(selected,original[-2:])
        self.assertEqual(tuple(r['id'] for r in selected),screen.REMAINING_IDS)
        self.assertNotIn('augnes-screen-1274',[r['id'] for r in selected])

    def test_completion_refuses_changed_evidence_or_a_finished_selected_slot(self):
        encoded={'overflow':False,'input_tokens':100,'token_ids_sha256':'a'*64}
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'recovery.json';raw=screen.RECOVERY.read_bytes();path.write_bytes(raw+b' ')
            with patch.object(screen,'RECOVERY',path),self.assertRaises(ValueError):
                screen.assigned_schedule(Mock())
            changed=json.loads(raw);changed['records'][-1]['status']='OK'
            path.write_text(json.dumps(changed))
            with patch.object(screen,'RECOVERY',path),\
                    patch.object(screen,'RECOVERY_SHA256',screen.life.digest(path.read_bytes())),\
                    patch.object(screen.ready,'encode',return_value=encoded),self.assertRaises(ValueError):
                screen.assigned_schedule(Mock())

    def test_teardown_observes_requested_worker_then_gpu(self):
        with patch.object(entry.remote,'remote',return_value={'same_process_alive':False}) as remote,\
                patch.object(entry.remote,'inventory',return_value={'uuid':'fixture'}) as inventory:
            observed=entry.check_stopped(['fixture'],'E2B-screening','fixture')
            self.assertIn('E2B-screening-state.json',remote.call_args.args[1])
            inventory.assert_called_once_with(['fixture'],'fixture')
            self.assertFalse(observed['worker']['same_process_alive'])
        with self.assertRaises(ValueError):entry.check_stopped([],'unknown','fixture')

    def test_post_update_probe_keeps_only_first_original_message_and_short_deadline(self):
        import sys,types
        module=types.ModuleType('transformers');module.AutoTokenizer=Mock()
        rows=[{'id':str(i),'model':'E2B','arm':'B0','messages':[{'role':'user','content':str(i)}]}
              for i in range(3)]
        with tempfile.TemporaryDirectory(dir=screen.ROOT/'.local') as td:
            root=Path(td);(root/'.local').mkdir();spec=root/'spec.json'
            spec.write_text(json.dumps({'prefix':['fixture'],'gpu_uuid':'fixture'}))
            with patch.object(entry,'ROOT',root),patch.dict(sys.modules,{'transformers':module}),\
                    patch.object(entry.runner,'load_scope',return_value=({},rows,{})),\
                    patch.object(entry,'replay_schedule') as replay,\
                    patch.object(entry.runner,'collect',return_value={'status':'COMPLETED'}) as collect,\
                    patch.object(entry.container,'ContainerChannel') as channel:
                entry.collect(spec,root,probe_only=True)
                args,kw=collect.call_args
                self.assertEqual(args[0],rows[:1]);replay.assert_not_called()
                factory=args[2];self.assertTrue(factory.training_requested)
                factory('E2B',root)
                self.assertIn('E2B-pretrained 240 pretrained',channel.call_args.args[0][-1])
                self.assertEqual(kw['total_seconds'],240)
                self.assertEqual(kw['max_new_tokens'],4096)


if __name__=='__main__':unittest.main()
