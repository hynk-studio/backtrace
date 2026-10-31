"""Actual kernel denial tracing, without requiring CUDA or ptrace privileges."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'linux' and shutil.which('gcc'), 'Linux C compiler required')
class DenialTraceTests(unittest.TestCase):
    def run_trace(self, body):
        with tempfile.TemporaryDirectory() as td:
            library = Path(td)/'denial-trace.so'
            subprocess.run(['gcc','-std=c11','-O2','-fPIC','-shared','-Wall','-Wextra','-Werror',
                '-o',str(library),str(ROOT/'tools/small_model_minimum_trace.c')],check=True,timeout=30)
            program = '''import ctypes,json,os,socket,threading
from tools.small_model_container_worker import restrict_syscalls
recorder=ctypes.CDLL(%r,use_errno=True)
assert recorder.backtrace_trace_install()==0
restrict_syscalls(trace_denials=True)
''' % str(library)
            result = subprocess.run([sys.executable,'-c',program+body],cwd=ROOT,
                                    capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        records = [json.loads(line.removeprefix('BACKTRACE_SECCOMP_DENIAL '))
                   for line in result.stderr.splitlines() if line.startswith('BACKTRACE_SECCOMP_DENIAL ')]
        return json.loads(result.stdout), records

    def test_denials_are_recorded_without_permitting_sockets_fork_or_exec(self):
        result, records = self.run_trace('''
result={}
for name,fn in [('socket',socket.socket),('unix',lambda:socket.socket(socket.AF_UNIX)),
                ('fork',os.fork),('exec',lambda:os.execve('/usr/bin/true',['true'],{}))]:
 try:fn();raise AssertionError('denied operation executed: '+name)
 except OSError as error:result[name]=error.errno
threads=[]
t=threading.Thread(target=lambda:threads.append(True));t.start();t.join(2)
result['thread']=threads==[True]
libc=ctypes.CDLL(None,use_errno=True)
result['clone3_return']=libc.syscall(435,0,0)
result['clone3_errno']=ctypes.get_errno()
print(json.dumps(result))
''')
        self.assertEqual(result,{'socket':1,'unix':1,'fork':1,'exec':1,'thread':True,
                                 'clone3_return':-1,'clone3_errno':38})
        self.assertEqual([r['syscall'] for r in records],[41,41])
        self.assertEqual([r['args'][0] for r in records[:2]],[2,1])
        self.assertTrue(all(r['errno']==1 for r in records))

    def test_log_cap_does_not_allow_later_denied_calls(self):
        result, records = self.run_trace('''
denied=0
for i in range(80):
 try:socket.socket();raise AssertionError('socket executed')
 except PermissionError:denied+=1
print(json.dumps({'denied':denied,'count':recorder.backtrace_trace_count()}))
''')
        self.assertEqual(result,{'denied':80,'count':80})
        self.assertEqual(len(records),64)

    def test_trap_without_handler_fails_closed(self):
        p=subprocess.run([sys.executable,'-c',
            'import socket;from tools.small_model_container_worker import restrict_syscalls;'
            'restrict_syscalls(trace_denials=True);socket.socket()'],cwd=ROOT,
            capture_output=True,timeout=10)
        self.assertEqual(p.returncode,-31)


if __name__=='__main__':unittest.main()
