"""Actual Linux negative controls for UID, network and process lifetime boundaries."""
import json
import os
from pathlib import Path
import shlex
import socket
import sys
import time

from tools import research_comparison as c
from tools.research_isolation import Isolation, bounded_child


def qualify(output):
    from swegemma.sandbox import SubprocessManager
    from swegemma.context import SwegemmaContext
    from swegemma.models import Task
    from swegemma.tools.execution import run_command
    output.mkdir(mode=0o711)
    private = output / 'private'; private.mkdir(mode=0o700)
    owner = private / 'owner-canary'; owner.write_text('owner-only'); owner.chmod(0o600)
    evaluator = output / 'evaluator'; evaluator.mkdir(mode=0o700); os.chown(evaluator, 65533, 65533)
    reference = evaluator / 'reference-canary'; reference.write_text('evaluator-only')
    os.chown(reference, 65533, 65533); reference.chmod(0o600)
    manager = SubprocessManager(timeout_seconds=60, base_dir=output / 'agent/sandboxes')
    isolation = Isolation(private / 'isolation', 65532); isolation.attach(manager)
    sid = manager.start(); checks = {}; observations = {}
    listeners = [socket.socket(), socket.socket()]
    try:
        for sock in listeners: sock.bind(('127.0.0.1', 0)); sock.listen()
        ports = [s.getsockname()[1] for s in listeners]
        code = '''import json,os,pathlib,socket
result={}
status=dict(line.split(':',1) for line in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in line)
result['uid']=os.getuid(); result['caps']=int(status['CapEff'].strip(),16); result['no_new_privs']=status['NoNewPrivs'].strip()=='1'
result['pid_ns']=os.readlink('/proc/self/ns/pid'); result['net_ns']=os.readlink('/proc/self/ns/net')
result['denied']=[]
for path in FILES:
 try: pathlib.Path(path).read_bytes(); result['denied'].append(False)
 except PermissionError: result['denied'].append(True)
result['ports_blocked']=[]
for port in PORTS:
 sock=socket.socket(); sock.settimeout(.2)
 try: sock.connect(('127.0.0.1',port)); result['ports_blocked'].append(False)
 except OSError: result['ports_blocked'].append(True)
 finally: sock.close()
s=socket.socket(); s.bind(('127.0.0.1',0)); s.listen(); t=socket.create_connection(s.getsockname(),timeout=1); a,_=s.accept(); a.close(); t.close(); s.close()
result['own_loopback']=True
print(json.dumps(result))'''.replace('FILES', repr([str(owner), str(reference)])).replace('PORTS', repr(ports))
        observed = manager.exec(sid, 'python3 -c ' + shlex.quote(code), timeout=10)
        c._new_output(private / 'boundaries.log', (observed.stdout + observed.stderr).encode())
        if observed.exit_code != 0: raise ValueError('boundary probe did not execute')
        facts = json.loads(observed.stdout)
        checks.update(dedicated_uid=facts['uid']==65532, capabilities_dropped=facts['caps']==0,
            no_new_privs=facts['no_new_privs'], reference_access_denied=all(facts['denied']),
            gateway_and_upstream_inaccessible=all(facts['ports_blocked']), own_loopback_available=facts['own_loopback'],
            distinct_pid_namespace=facts['pid_ns']!=os.readlink('/proc/self/ns/pid'),
            distinct_network_namespace=facts['net_ns']!=os.readlink('/proc/self/ns/net'))
        workspace = manager.sandboxes[sid]['workspace']
        (workspace / 'link').symlink_to(owner)
        try:
            manager.copy_from(sid, '/workspace/link', private / 'should-not-exist')
            checks['tool_symlink_read_denied'] = False
        except (OSError, ValueError): checks['tool_symlink_read_denied'] = True
        try:
            manager.copy_to(sid, reference, '/workspace/link')
            checks['tool_symlink_write_denied'] = False
        except (OSError, ValueError): checks['tool_symlink_write_denied'] = True
        checks['owner_file_unchanged'] = owner.read_text() == 'owner-only'
        # A real official run_command, not a replacement timeout implementation.
        context = SwegemmaContext(task=Task(instance_id='fixture_1', repo='fixture/repo',
            base_commit='0'*40, problem_statement='CPU boundary probe'),
            task_id='fixture_1', repo='fixture/repo')
        context.docker = manager; context.container_id = sid; context.start_agent_session()
        # This exercises the same timer/command path with a 0.5-second allowance;
        # production uses the fixed 300-second allowance, never a late first request.
        isolation.begin(context.agent_start_time, seconds=.5)
        late = workspace / 'late-write'
        child = "import pathlib,time; time.sleep(1.5); pathlib.Path('late-write').write_text('escaped')"
        command = ('python3 -c ' + shlex.quote('import subprocess,time; subprocess.Popen(["python3","-c",'
            + repr(child) + '],start_new_session=True); time.sleep(30)'))
        started = time.perf_counter()
        try: result = run_command(context, command=command)
        except Exception as error: result = type(error).__name__
        observations['inflight_elapsed_seconds'] = time.perf_counter()-started
        c._new_output(private / 'deadline-tool.json', str(result).encode())
        time.sleep(1.6)
        checks['inflight_command_stopped'] = observations['inflight_elapsed_seconds'] < 2
        checks['detached_descendant_stopped'] = not late.exists()
        checks['deadline_recorded'] = isolation.expired
        checks['namespace_stopped'] = isolation.report()['live_namespaces']==0
    finally:
        for sock in listeners: sock.close()
        manager.close(); isolation.finish()
    # Independently exercise the outer 330-second envelope at a scaled 0.5 s.
    marker = private / 'outer-late'
    child = 'import pathlib,time; time.sleep(1.5); pathlib.Path('+repr(str(marker))+').write_text("late")'
    code = 'import subprocess,time; subprocess.Popen(['+repr(sys.executable)+',"-c",'+repr(child)+'],start_new_session=True); time.sleep(30)'
    outer = bounded_child([sys.executable, '-I', '-c', code], private/'outer.log',
                          {'PATH': '/usr/bin:/bin'}, timeout=.5)
    time.sleep(1.6)
    checks['outer_deadline_tree_killed'] = outer['child_timeout'] and not marker.exists() and outer['wall_seconds']<2
    checks['workspace_cleanup'] = not manager.sandboxes
    report = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
              'observations': observations, 'outer_child': outer, 'isolation': isolation.report(),
              'scope': 'actual CPU mechanisms; scaled 0.5-second deadline controls; no GPU claim'}
    c._new_output(output / 'receipt.json', c.encoded(report))
    return report
