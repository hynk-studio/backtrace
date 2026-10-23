"""Real nested Linux ownership probe; authored payload, no GPU/model/provider."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.startup_guard import guarded_server, group_members


def flag(value=None):
    libc = ctypes.CDLL(None, use_errno=True)
    if value is None:
        result = ctypes.c_int()
        if libc.prctl(37, ctypes.byref(result), 0, 0, 0): raise OSError(ctypes.get_errno(), 'get subreaper')
        return result.value
    if libc.prctl(36, value, 0, 0, 0): raise OSError(ctypes.get_errno(), 'set subreaper')


def process_row(pid):
    try:
        data = Path('/proc') / str(pid) / 'stat'
        fields = data.read_text().rpartition(') ')[2].split()
        return {'pid': pid, 'state': fields[0], 'ppid': int(fields[1]), 'pgid': int(fields[2])}
    except (FileNotFoundError, ProcessLookupError): return None


class Payload:
    def __init__(self, directory):
        self.config = SimpleNamespace(startup_timeout=12)
        self.log_path = str(directory / 'server.log'); self.process = None; self._log_file_handle = None
    def build_cmd(self):
        child = "import time;time.sleep(60)"
        engine = ("import subprocess,sys,json,time; p=subprocess.Popen([sys.executable,'-c'," + repr(child)
            + "],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);print(json.dumps({'child':p.pid}),flush=True);time.sleep(.15)")
        return [sys.executable, '-I', '-c', engine]
    def start(self):
        self._log_file_handle = open(self.log_path, 'w')
        self.process = subprocess.Popen(self.build_cmd(), stdout=self._log_file_handle, stderr=subprocess.STDOUT)
        until = time.monotonic() + 8
        while time.monotonic() < until:
            if self.is_healthy(): break
            time.sleep(.01)
        else: raise RuntimeError('payload marker deadline')
        self.process.wait(timeout=5)
        return self
    def is_healthy(self):
        try:
            self.child = json.loads(Path(self.log_path).read_text().splitlines()[0])['child']; return True
        except (ValueError, IndexError): return False
    def stop(self, timeout=1):
        if self._log_file_handle: self._log_file_handle.close(); self._log_file_handle = None
        if self.process: self.process.wait(timeout=timeout); self.process = None


def phase(directory, outer_pid):
    before = flag()
    cls = guarded_server(Payload, total_deadline=time.monotonic() + 15, error_type=RuntimeError)
    server = cls(directory); server.start(); pgid = server.process.pid; child = server.child
    started_flag = flag(); started = time.monotonic(); error = None
    try: server.stop()
    except RuntimeError as caught: error = str(caught)
    row = process_row(child)
    result = {'phase_uid': os.getuid(), 'phase_pid': os.getpid(), 'outer_pid': outer_pid,
        'subreaper_before': before, 'subreaper_after_start': started_flag,
        'subreaper_after_stop': flag(), 'cleanup_error': error, 'seconds': time.monotonic() - started,
        'remaining_child': row, 'group_members_after_stop': group_members(pgid), 'pgid': pgid,
        'startup_observation': server.startup_observation}
    # Writer cleanup cannot reap a child owned by the outer subreaper.
    if server._log_file_handle: server._log_file_handle.close()
    print(json.dumps(result, sort_keys=True))


def probe(expect):
    from tools.runpod_job import check_owner_host
    check_owner_host()
    original = flag(); flag(1); report = None; reaped = []
    try:
        with tempfile.TemporaryDirectory(prefix='nested-reaper-') as directory:
            os.chown(directory, 65534, 65534)
            def drop(): os.setgroups([]); os.setgid(65534); os.setuid(65534)
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--phase', directory, str(os.getpid())],
                preexec_fn=drop, capture_output=True, text=True, check=True, timeout=20)
            report = json.loads(result.stdout.splitlines()[-1])
            until = time.monotonic() + 3
            while time.monotonic() < until:
                try: pid, _ = os.waitpid(-1, os.WNOHANG)
                except ChildProcessError: break
                if pid: reaped.append(pid)
                else: time.sleep(.01)
            report.update(outer_subreaper=1, outer_reaped=reaped,
                final_group_members=group_members(report['pgid']), expect=expect,
                gpu_allocations=0, model_calls=0, boundary='authored payload; real nested Linux UID/subreaper/process groups')
            assert report['phase_uid'] == 65534 and report['subreaper_before'] == 0
            assert report['final_group_members'] == []
            if expect == 'orphan-error':
                assert 'owned startup process group did not disappear' in (report['cleanup_error'] or '')
                assert report['remaining_child']['state'] == 'Z' and report['remaining_child']['ppid'] == os.getpid()
                assert report['remaining_child']['pid'] in reaped
            else:
                assert report['cleanup_error'] is None and report['group_members_after_stop'] == []
                assert report['remaining_child'] is None and report['subreaper_after_stop'] == 0
                assert reaped == []
            report['status'] = 'PASS'
    finally:
        # Only direct children of this test process can be targeted/reaped here.
        for path in Path('/proc').iterdir():
            if path.name.isdecimal():
                row = process_row(int(path.name))
                if row and row['ppid'] == os.getpid():
                    try: os.kill(row['pid'], signal.SIGKILL)
                    except ProcessLookupError: pass
        try:
            while os.waitpid(-1, os.WNOHANG)[0]: pass
        except ChildProcessError: pass
        flag(original)
    return report


if __name__ == '__main__':
    if sys.argv[1:2] == ['--phase']:
        phase(Path(sys.argv[2]), int(sys.argv[3]))
    else:
        parser = argparse.ArgumentParser(); parser.add_argument('--expect', choices=('orphan-error', 'clean'), required=True)
        print(json.dumps(probe(parser.parse_args().expect), sort_keys=True))
