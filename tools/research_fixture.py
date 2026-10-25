"""Authored CPU HTTP responses exercise the official runner, never a model.

Each child owns one fresh task/arm and is bounded by the parent to 330 seconds.
Responses test transport/tool plumbing only and do not solve the public tasks.
"""
import argparse
import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import research_comparison as c
from tools.research_runner import checked_slot, run_slot

MARKER = 'backtrace-authored-cpu-fixture.txt'
USAGE = {'prompt_tokens': 11, 'completion_tokens': 7, 'total_tokens': 18,
         'completion_tokens_details': {'reasoning_tokens': 3},
         'prompt_tokens_details': {'cached_tokens': 0}}


def run_fixture(inputs, output, identifier, arm, wheels, control='ordinary', *, isolation=None,
                upstream=None, fixture_port=0, qualification_seconds=None):
    from swegemma.graph.graph_utils import get_graph
    import numpy as np
    task, _ = checked_slot(inputs, identifier, arm)
    graph = get_graph(task['repo'], graph_dir=str(inputs / 'assets/graphs'),
                      embeddings_dir=str(inputs / 'assets/embeddings'), base_commit=task['base_commit'])
    vectors = [attributes.get('embedding') for _, attributes in graph.nodes(data=True)]
    valid_vectors = [v for v in vectors if isinstance(v, np.ndarray) and v.size and np.isfinite(v).all()]
    dimensions = sorted({int(v.size) for v in valid_vectors})
    asset_check = {'nodes': len(vectors), 'edges': graph.number_of_edges(),
                   'finite_embeddings': len(valid_vectors), 'embedding_dimensions': dimensions}
    counts = {'root': 0, 'delegate': 0, 'compaction': 0}; failures = []; roles = []
    class Endpoint(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            try:
                body = c.parse(self.rfile.read(int(self.headers['Content-Length'])))
                if control == 'retry' and not roles:
                    roles.append('failed_attempt')
                    data = b'{"error":{"message":"authored retry control","type":"InternalServerError"}}'
                    self.send_response(500); self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
                    return
                names = {t['function']['name'] for t in body.get('tools', [])}
                role = 'compaction' if not names else 'root' if 'submit_patch' in names else 'delegate'
                counts[role] += 1; step = counts[role]; roles.append(role)
                if ((control == 'deadline_before_submit' and role == 'root' and step == 2)
                        or (control in ('deadline_after_submit', 'outer_after_submit')
                            and role == 'root' and step == 4)):
                    # The actual original tool has already run. Wait for the
                    # transport to close, not an arbitrary wall-clock sleep.
                    self.connection.settimeout(45)
                    self.connection.recv(1)
                    return
                # Inspect only fixture tool acknowledgements, never task labels.
                if step > 1 and role != 'compaction':
                    acknowledgements = [m for m in body['messages'] if m['role'] == 'tool']
                    if not acknowledgements:
                        raise ValueError('missing real tool acknowledgement')
                    content = acknowledgements[-1]['content']
                    if '"status": "error"' in content or '"status":"error"' in content:
                        raise ValueError('fixture tool execution failed')
                name = None; arguments = {}
                if role == 'root':
                    if step == 1:
                        name = 'run_command'
                        command = ("python3 -c \"from pathlib import Path; p=Path('" + MARKER
                                   + "'); assert not p.exists(); p.write_text('authored CPU fixture\\n')\"")
                        arguments = {'command': command}
                    elif step == 2:
                        name = 'code_analyzer_agent'; arguments = {'request': 'Read ' + MARKER + ' and report its contents.'}
                    elif step == 3:
                        name = 'submit_patch'
                    elif step != 4:
                        raise ValueError('unexpected extra root request')
                elif role == 'delegate':
                    if step == 1:
                        name = 'read_file'; arguments = {'filepath': MARKER}
                    elif step == 2:
                        content = acknowledgements[-1]['content']
                        if 'authored CPU fixture' not in content:
                            raise ValueError('delegate did not read the new workspace marker')
                    else:
                        raise ValueError('unexpected extra delegate request')
                elif control != 'compaction' or step > 2:
                    raise ValueError('unexpected compaction request')
                if name and name not in names:
                    raise ValueError('required original tool missing')
                message = {'role': 'assistant', 'content': None if name else 'Authored CPU fixture complete.'}
                if name:
                    message['tool_calls'] = [{'id': 'fixture_' + role + str(step), 'type': 'function',
                        'function': {'name': name, 'arguments': json.dumps(arguments)}}]
                usage = dict(USAGE)
                if control == 'compaction' and role == 'root' and step == 2:
                    usage.update(prompt_tokens=15000, total_tokens=15007)
                envelope = {'id': 'cpu_' + str(len(roles)), 'created': 1, 'model': body['model'],
                            'object': 'chat.completion', 'choices': [{'index': 0, 'message': message,
                            'finish_reason': 'tool_calls' if name else 'stop'}], 'usage': usage}
                if body.get('stream'):
                    if body.get('stream_options') != {'include_usage': True}:
                        raise ValueError('stream usage was not requested')
                    chunk = {k: v for k, v in envelope.items() if k not in ('choices', 'usage')}
                    chunk['object'] = 'chat.completion.chunk'
                    delta = dict(message)
                    if name:
                        delta['tool_calls'][0]['index'] = 0
                    chunk['choices'] = [{'index': 0, 'delta': delta, 'finish_reason': None}]
                    terminal = {**chunk, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': envelope['choices'][0]['finish_reason']}], 'usage': usage}
                    data = ('data: ' + json.dumps(chunk) + '\n\ndata: ' + json.dumps(terminal) + '\n\ndata: [DONE]\n\n').encode()
                    content_type = 'text/event-stream'
                else:
                    data = json.dumps(envelope).encode(); content_type = 'application/json'
                self.send_response(200); self.send_header('Content-Type', content_type)
            except Exception as error:
                failures.append(type(error).__name__ + ': ' + str(error))
                data = b'{"error":{"message":"authored fixture mismatch","type":"BadRequestError"}}'
                self.send_response(400); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', fixture_port), Endpoint)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        result = run_slot(inputs, output, identifier, arm, None if upstream else server.server_port,
            wheels, isolation=isolation, upstream=upstream, qualification_seconds=qualification_seconds)
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)
    meter = result['accounting']
    checks = {'official_completed': result['status'] == 'COMPLETED',
        'official_graph_and_embeddings': len(vectors) > 0 and len(valid_vectors) == len(vectors) and len(dimensions) == 1,
        'fresh_workspace_patch': result.get('patch_bytes', 0) > 0 and MARKER in (output / 'agent.patch').read_text(),
        'root_delegate_http_counts': counts == {'root': 4, 'delegate': 2, 'compaction': int(control == 'compaction')}
            and meter['admitted_requests'] == (6 if control == 'ordinary' else 7),
        'two_charged_original_tools': result.get('charged_tool_calls') == 2,
        'sampling_accepted': meter['rejected_requests'] == 0,
        'tokens_match_fixture': meter['token_accounting'] == 'COMPLETE' and meter['totals'] ==
            ({'prompt_tokens': 15066, 'completion_tokens': 49, 'total_tokens': 15115, 'reasoning_tokens': 21, 'cached_tokens': 0}
             if control == 'compaction' else
             {'prompt_tokens': 66, 'completion_tokens': 42, 'total_tokens': 108, 'reasoning_tokens': 18, 'cached_tokens': 0}),
        'cleanup': result.get('sandbox_cleanup') and meter['closed'] and not thread.is_alive(),
        'fixture_contract': not failures}
    if isolation is not None:
        checks['os_cleanup'] = (result['isolation']['live_namespaces'] == 0
                                and result['isolation']['closed_namespaces'] == 1)
    if control == 'retry':
        checks['tokens_match_fixture'] = (meter['token_accounting'] == 'INCOMPLETE'
            and all(v is None for v in meter['totals'].values())
            and meter['requests'][0]['http_status'] == 500
            and meter['requests'][0]['usage']['status'] == 'MISSING_OR_INVALID')
    if control == 'compaction':
        checks['compaction_in_same_allowance'] = (roles.count('compaction') == 1
            and any(r['applied_frozen_defaults'] for r in meter['requests']))
    if control in ('deadline_before_submit', 'deadline_after_submit'):
        submitted = control == 'deadline_after_submit'
        checks = {'actual_work_deadline': result['status']=='TIMEOUT' and result['isolation']['deadline_expired'],
            'submitted_patch_preserved': bool(result.get('patch_submitted')) == submitted
                and (result.get('patch_bytes', 0)>0) == submitted,
            'unsubmitted_diff_explicit': submitted or result.get('unsubmitted_diff')=='UNAVAILABLE_AFTER_ISOLATION_STOP',
            'accounting_not_fabricated': meter['token_accounting']=='INCOMPLETE'
                and all(v is None for v in meter['totals'].values()),
            'closed_and_cleaned': result['sandbox_cleanup'] and meter['closed']
                and result['isolation']['live_namespaces']==0 and not thread.is_alive(),
            'retained_trace': bool(list((output/'results').glob('*'))),
            'fixture_contract': not failures}
    report = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
              'model_execution': 'AUTHORED_CPU_HTTP_ONLY', 'real_model_runs': 0,
              'control': control, 'request_roles': roles, 'fixture_errors': failures, 'asset_readiness': asset_check, 'slot': result}
    c._new_output(output / 'fixture-receipt.json', c.encoded(report))
    return report


def qualify(python, inputs, output, wheels, env):
    output.mkdir(mode=0o700)
    selection = c.parse((c.ROOT / 'docs/research-selection-20261024.json').read_bytes())
    def execute(identifier, arm, name, control='ordinary'):
        destination = output / name
        started = time.perf_counter()
        with (output / (name + '.log')).open('wb') as stream:
            process = subprocess.Popen([str(python), '-I', '-B', str(Path(__file__).resolve()),
                str(inputs), str(destination), identifier, arm, str(wheels), '--control', control],
                env=env, stdin=subprocess.DEVNULL, stdout=stream, stderr=stream, start_new_session=True)
            expired = False
            try:
                code = process.wait(timeout=330)
            except subprocess.TimeoutExpired:
                expired = True; os.killpg(process.pid, signal.SIGKILL); code = process.wait(timeout=10)
        receipt = destination / 'fixture-receipt.json'
        row = {'instance_id': identifier, 'arm': arm, 'exit_code': code,
               'child_timeout': expired, 'wall_seconds': time.perf_counter() - started}
        if receipt.exists():
            row['fixture'] = c.parse(receipt.read_bytes())
        row['status'] = 'PASS' if code == 0 and not expired and row.get('fixture', {}).get('status') == 'PASS' else 'FAIL'
        return row
    reports = []
    for task in selection['primary']:
        for arm in task['arm_order']:
            row = execute(task['instance_id'], arm, task['instance_id'] + '-' + arm)
            reports.append(row)
            if row['status'] != 'PASS':
                break
        if reports[-1]['status'] != 'PASS':
            break
    controls = []
    if len(reports) == 18 and all(r['status'] == 'PASS' for r in reports):
        for name in ('retry', 'compaction'):
            controls.append(execute(selection['primary'][0]['instance_id'], 'R0', 'control-' + name, name))
    passed = len(reports) == 18 and len(controls) == 2 and all(r['status'] == 'PASS' for r in reports + controls)
    return {'status': 'PASS' if passed else 'FAIL',
            'scope': 'OFFICIAL_RUNNER_SCRIPTED_CPU_TRANSPORT', 'real_model_runs': 0,
            'planned_slots': 18, 'completed_slots': len(reports), 'slots': reports,
            'additional_transport_controls': controls}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path); parser.add_argument('output', type=Path)
    parser.add_argument('identifier'); parser.add_argument('arm'); parser.add_argument('wheels', type=Path)
    parser.add_argument('--control', choices=('ordinary', 'retry', 'compaction'), default='ordinary')
    args = parser.parse_args()
    result = run_fixture(args.inputs, args.output, args.identifier, args.arm, args.wheels, args.control)
    print(json.dumps({'status': result['status'], 'instance_id': args.identifier, 'arm': args.arm}))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
