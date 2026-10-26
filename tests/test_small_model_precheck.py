"""Free contract/failure controls. No physical GPU or live provider calls."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from tools import small_model_lifecycle as life, small_model_resources as res
from tools import small_model_precheck as pre


class ClockTests(unittest.TestCase):
    def test_allocation_time_includes_elapsed_setup_and_uses_monotonic(self):
        wall = [100.]; mono = [20.]
        clock = life.Deadline(80, 100, wall=lambda: wall[0], mono=lambda: mono[0])
        self.assertEqual(clock.remaining(30), 50)
        mono[0] += 12  # A stalled wall clock cannot grant extra run time.
        self.assertEqual(clock.remaining(30), 38)
        wall[0] += 60
        self.assertEqual(clock.remaining(30), -10)

    def test_reversed_clock_and_invalid_timestamps_fail_closed(self):
        wall = [100]
        clock = life.Deadline(90, 100, wall=lambda: wall[0], mono=lambda: 0)
        wall[0] = 99
        with self.assertRaises(TimeoutError): clock.remaining()
        for start, total in [(101, 100), (0, 100), (90, float('nan')), (True, 100), (90, 3001)]:
            with self.subTest(start=start, total=total), self.assertRaises(ValueError):
                life.Deadline(start, total, wall=lambda: 100, mono=lambda: 0)

    def test_expired_resource_gets_cleanup_only_allowance(self):
        clock = life.Deadline(80, 10, wall=lambda: 100, mono=lambda: 0, allow_expired=True)
        self.assertLess(clock.remaining(3), 0)
        with patch.object(life.time, 'monotonic', return_value=0):
            self.assertEqual(life.cleanup_allowance(clock, {'cleanup_seconds': 3}), 3)


class MemoryTests(unittest.TestCase):
    def test_ancestor_headroom_and_high_limits_override_host_ram(self):
        levels = [{'path': '/parent/child', 'memory.current': 2*res.GIB,
                   'memory.max': 64*res.GIB, 'memory.high': 'max'},
                  {'path': '/parent', 'memory.current': 20*res.GIB,
                   'memory.max': 48*res.GIB, 'memory.high': 36*res.GIB}]
        value = res.assess('MemTotal: 134217728 kB\nMemAvailable: 67108864 kB\n', levels,
                           minimum_bytes=32*res.GIB)
        self.assertEqual(value['conservative_available_bytes'], 16*res.GIB)
        self.assertEqual(value['status'], 'INSUFFICIENT')
        self.assertFalse(value['swap_counted_as_ram'])

    def test_actual_process_cgroup_mapping(self):
        member, mount = res.locate('0::/user.slice/a\n',
            '1 0 0:1 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n')
        self.assertEqual(member, Path('/sys/fs/cgroup/user.slice/a'))
        self.assertEqual(mount, Path('/sys/fs/cgroup'))

    def test_hidden_ancestors_legacy_and_ambiguous_mounts_rejected(self):
        mount = '1 0 0:1 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n'
        for group, mounts in [('1:memory:/a', mount), ('0::/../../hidden', mount),
                              ('0::/a', mount*2), ('0::/a', mount.replace(' / ', ' /hidden '))]:
            with self.subTest(group=group), self.assertRaises(ValueError): res.locate(group, mounts)

    def test_missing_available_memory_and_invalid_limits_rejected(self):
        with self.assertRaises(ValueError): res.assess('MemTotal: 1 kB\n', [], minimum_bytes=1)
        row = {'memory.current': True, 'memory.max': 'max', 'memory.high': 'max'}
        with self.assertRaises(ValueError):
            res.assess('MemTotal: 1 kB\nMemAvailable: 1 kB\n', [row], minimum_bytes=1)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.work = self.root/'work'; self.work.mkdir()
    def tearDown(self): self.tmp.cleanup()

    def test_allowlist_manifest_and_no_weight_prompt_or_job_export(self):
        for name in ('receipt.json', 'ledger.jsonl', 'prompt.json', 'model.safetensors', 'job.json'):
            (self.work/name).write_text(name)
        private = self.work/'private'; private.mkdir(); (private/'receipt.json').write_text('secret')
        report = life.export(self.work, self.root/'out.tar')
        self.assertEqual({r['path'] for r in report['files']}, {'receipt.json', 'ledger.jsonl'})
        with tarfile.open(self.root/'out.tar') as tar:
            manifest = json.load(tar.extractfile('manifest.json'))
            for row in manifest['files']:
                self.assertEqual(life.digest(tar.extractfile(row['path']).read()), row['sha256'])
        self.assertFalse(report['uploaded'])

    def test_symlink_hardlink_and_oversize_rejected(self):
        p = self.work/'receipt.json'; p.symlink_to('/etc/hosts')
        with self.assertRaises(ValueError): life.export(self.work, self.root/'out.tar')
        p.unlink(); p.write_text('x'); os.link(p, self.root/'other')
        with self.assertRaises(ValueError): life.export(self.work, self.root/'out.tar')
        (self.root/'other').unlink()
        with p.open('wb') as f: f.truncate(16*1024**2+1)
        with self.assertRaises(ValueError): life.export(self.work, self.root/'out.tar')

    def test_export_destination_cannot_enter_source_and_files_are_create_only(self):
        (self.work/'receipt.json').write_text('{}')
        with self.assertRaises(ValueError): life.export(self.work, self.work/'receipt.tar')
        life.export(self.work, self.root/'out.tar')
        with self.assertRaises(FileExistsError): life.export(self.work, self.root/'out.tar')


class ResourceTests(unittest.TestCase):
    def test_atomic_heartbeat_replacement_retains_opened_complete_inode(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); root.chmod(0o700); journal = life.Journal(root)
            p = journal.path('owner-heartbeat'); replacement = root/'replacement'
            life.write(p, {'at': 1}); life.write(replacement, {'at': 2})
            original = os.open
            def opened(path, *args, **kwargs):
                fd = original(path, *args, **kwargs)
                if Path(path) == p: os.replace(replacement, p)
                return fd
            with patch.object(os, 'open', side_effect=opened):
                self.assertEqual(journal.read('owner-heartbeat'), {'at': 1})
            self.assertEqual(journal.read('owner-heartbeat'), {'at': 2})

    def test_failed_get_or_mismatched_list_never_proves_absence(self):
        identity = {'id': 'owned', 'name': 'backtrace-small-'+'a'*32}
        class API:
            def list(self): return [identity]
            def get(self, _): return None
            def delete(self, _): raise AssertionError('must not delete ambiguous identity')
        resource = life.RunpodResource(API(), identity)
        with self.assertRaises(ValueError): resource.observe()
        result = life.cleanup(resource, .025, interval=.005)
        self.assertEqual(result['status'], 'UNRESOLVED')
        self.assertEqual(result['absence_reads'], 0)

    def test_false_delete_ack_is_observed_again_and_two_absences_required(self):
        class Resource:
            deletes = 0
            def observe(self): return self.deletes < 2
            def delete(self): self.deletes += 1
        resource = Resource(); result = life.cleanup(resource, .5, interval=.005)
        self.assertEqual(resource.deletes, 2)
        self.assertEqual(result['absence_reads'], 2)
        self.assertEqual([r['state'] for r in result['history']], ['PRESENT', 'PRESENT', 'ABSENT', 'ABSENT'])

    def test_resource_adapter_has_no_allocation_capability(self):
        self.assertFalse(hasattr(life.RunpodResource, 'create'))

    def test_new_minimum_plan_excludes_weights_and_preserves_original_baseline(self):
        with tempfile.TemporaryDirectory() as name:
            plan = pre.prepare(Path(name)/'plan.json')
        self.assertEqual(plan['minimum_scope']['pretrained_requests'], 0)
        self.assertEqual(plan['minimum_scope']['weight_download_bytes'], 0)
        self.assertEqual(plan['future_baseline']['requests'], 36)
        self.assertFalse(plan['paid_authorization'])
        self.assertEqual(plan['limits']['work_stop_elapsed_seconds'], 2580)
        self.assertEqual(plan['launch_gate']['status'], 'BLOCKED')

    def test_cuda_hold_uses_qualified_worker_checks_without_running_them(self):
        with tempfile.TemporaryDirectory() as name:
            path = pre._context_worker(Path(name)); code = path.read_text()
            compile(code, str(path), 'exec')
            self.assertIn('facts=cuda_check(job)', code)
            self.assertIn('CPU fallback forbidden', code)
            self.assertNotIn("if __name__", code)


if __name__ == '__main__': unittest.main()
