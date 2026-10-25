import copy
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tools import research_reduced as reduced, research_entry_contract as c
from tools.research_entry import binding
from tools.research_reduced_evaluation import deletion_proof, patches
from tests.research_entry_replica import authorization, offer


class ReducedTests(unittest.TestCase):
    def test_selection_is_prospective_unique_repositories_and_balanced_positions(self):
        value=reduced.load();tasks=value['primary']
        self.assertEqual([r['instance_id'] for r in tasks],['requests_7309','rich_3486','httpx_3672'])
        self.assertEqual(len({r['repo'] for r in tasks}),3)
        for position in range(3):
            self.assertEqual({r['arm_order'][position] for r in tasks},{'R0','R1','R2'})
        self.assertFalse(value['selection_uses_model_outcomes'])
        self.assertEqual(4020+9*(330+10)+360+300,value['total_seconds'])

    def test_sequence_keeps_nine_denominators_after_failure(self):
        calls=[]
        def execute(identifier,arm,seconds):
            calls.append((identifier,arm,seconds))
            if len(calls)==2:raise RuntimeError('fixture')
            return {'status':'COMPLETED'}
        result=reduced.sequence(execute,deadline=7740,clock=lambda:0)
        self.assertEqual(len(result['slots']),9)
        self.assertEqual(len(calls),2)
        self.assertEqual(result['slots'][1]['status'],'INFRASTRUCTURE_FAILURE')
        self.assertTrue(all(r['status']=='NOT_RUN' for r in result['slots'][2:]))
        self.assertFalse(result['all_slots_attempted'])

    def test_next_slot_does_not_consume_export_or_cleanup_reserve(self):
        execute=mock.Mock()
        result=reduced.sequence(execute,deadline=999,clock=lambda:0)
        execute.assert_not_called()
        self.assertEqual(len(result['slots']),9)
        self.assertTrue(all(r['status']=='NOT_RUN' for r in result['slots']))

    def test_real_observed_credit_funds_full_conservative_window_without_top_up(self):
        permit=dict(authorization('a'*40),mode='OWNER_APPROVED_PAID',prior_spend_floor='5.0062308114')
        observed=dict(offer(),credit_balance='4.9937691886',compute_per_hour='1.986')
        c.permit(permit,'a'*40,time.time())
        self.assertEqual(c.costs(observed,permit,time.time())['maximum_all_in'],'4.300')
        for value in (dict(permit,additional_cap='4.31'),dict(permit,cumulative_cap='9.51'),
                      dict(permit,account_funded_total='10.01')):
            with self.assertRaises(ValueError):c.permit(value,'a'*40,time.time())
        with self.assertRaises(ValueError):c.costs(observed,permit,time.time(),seconds=7741)
        with self.assertRaises(ValueError):c.costs(dict(observed,credit_balance='4.79'),permit,time.time())

    def test_shared_github_quota_includes_both_controllers_and_retry_reserve(self):
        rate={'limit':1000,'remaining':950,'reset':4600,'observed_at':1000,'resource':'core'}
        budget=c.github_budget(rate,1000)
        self.assertEqual(budget['required_until_reset'],900)
        self.assertEqual(budget['nominal_combined_requests_per_hour'],560)
        self.assertEqual(budget['reserved_combined_requests_per_hour'],800)
        for change in ({'remaining':899},{'observed_at':900},{'resource':'search'},
                       {'reset':999},{'limit':60}):
            with self.assertRaises(ValueError):c.github_budget(dict(rate,**change),1000)
        with self.assertRaises(ValueError):c.github_budget(None,1000)

    def test_evaluation_requires_two_matching_deletions_not_one(self):
        claim={'fixture':'single-claim'}
        cleanup={'status':'DELETED','absence_reads':2,'claim_sha256':binding(claim),'pod_id':'fixture','completed_at':100}
        owner={'claim':claim,'cleanup':cleanup}
        self.assertEqual(deletion_proof(owner,cleanup)['status'],'PASS')
        for changes in ({'status':'UNRESOLVED'},{'absence_reads':1},{'claim_sha256':'wrong'},{'pod_id':'other'}):
            with self.assertRaises(ValueError):deletion_proof(owner,dict(cleanup,**changes))

    def test_missing_or_reordered_patch_slots_cannot_shrink_denominator(self):
        slots=reduced.sequence(lambda *_:None,deadline=0)['slots']
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            rows=patches(root,root,slots)
            self.assertEqual(len(rows),9)
            self.assertTrue(all(r['status']=='NOT_EVALUATED' for r in rows))
            for changed in (slots[:-1],list(reversed(slots))):
                with self.assertRaises(ValueError):patches(root,root,changed)

    def test_submitted_patch_must_match_retained_receipt_hash(self):
        slots=reduced.sequence(lambda *_:None,deadline=0)['slots']
        slots[0]['result']={'patch_submitted':True}
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path=root/'requests_7309-R0';path.mkdir();(path/'agent.patch').write_text('tampered')
            with mock.patch('tools.research_reduced_evaluation.checked_slot',return_value=({}, {'agent_task_sha256':'bound'})):
                with self.assertRaises(ValueError):patches(root,root,slots)
