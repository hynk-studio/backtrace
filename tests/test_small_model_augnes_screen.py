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
                    patch.object(screen,'schedule',return_value=[{'model':'E2B','arm':'B1','id':'fixture'}]),\
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

    def test_teardown_observes_requested_worker_then_gpu(self):
        with patch.object(entry.remote,'remote',return_value={'same_process_alive':False}) as remote,\
                patch.object(entry.remote,'inventory',return_value={'uuid':'fixture'}) as inventory:
            observed=entry.check_stopped(['fixture'],'E2B-screening','fixture')
            self.assertIn('E2B-screening-state.json',remote.call_args.args[1])
            inventory.assert_called_once_with(['fixture'],'fixture')
            self.assertFalse(observed['worker']['same_process_alive'])
        with self.assertRaises(ValueError):entry.check_stopped([],'unknown','fixture')


if __name__=='__main__':unittest.main()
