"""Small allowlisted observations of provider readiness; never raw Pod/log dumps."""
import hashlib
import json
import queue
import re
import threading

from tools.ssh_bootstrap import validate_endpoint

DEADLINE_SECONDS = 1200
POLL_SECONDS = 20
STATUSES = frozenset(('PROVISIONING', 'STARTING', 'RUNNING', 'EXITED', 'ERROR', 'TERMINATED'))
TERMINAL = frozenset(('EXITED', 'ERROR', 'TERMINATED'))
MAX_LOG_BYTES = 32768


def sample_logs(api, pod_id, *, timeout=4):
    """A diagnostic stream cannot hold the cleanup path, even during a stall."""
    output = queue.Queue(maxsize=1)
    def read():
        try:
            sample = api.bootstrap_logs(pod_id)
        except Exception as error:
            status = getattr(error, 'http_status', None)
            sample = {'status': 'UNAVAILABLE',
                      'http_status': status if type(status) is int else None}
        output.put(sample)
    # A stuck diagnostic GET has no mutation capability and must not keep the
    # owner process alive or block its stop/delete requests on the main thread.
    threading.Thread(target=read, daemon=True).start()
    try:
        return output.get(timeout=timeout)
    except queue.Empty:
        return {'status': 'TIME_LIMIT', 'budget_seconds': timeout}


def observe(pod, elapsed):
    """Expose state/endpoint validity, excluding addresses, env, args and URLs."""
    row = {'elapsed_seconds': max(0, int(elapsed))}
    if pod is None:
        return dict(row, provider_status='ABSENT', readiness='POD_ABSENT')
    if not isinstance(pod, dict):
        return dict(row, provider_status='UNKNOWN', readiness='UNKNOWN_PROVIDER_STATE')
    status = pod.get('status')
    if not isinstance(status, str):
        status = None
    row['provider_status'] = status if status in STATUSES else 'UNKNOWN'
    ssh = pod.get('ssh')
    direct = ssh.get('direct') if isinstance(ssh, dict) else None
    row['direct_endpoint_present'] = direct is not None
    valid = False
    if isinstance(direct, dict) and direct.get('username') == 'root':
        try:
            validate_endpoint(direct.get('host'), direct.get('port'))
            valid = True
        except (ValueError, TypeError):
            pass
    row['direct_endpoint_valid'] = valid
    row['started_at_present'] = pod.get('startedAt') is not None
    runtime = pod.get('runtime')
    row['runtime_present'] = isinstance(runtime, dict)
    if status not in STATUSES:
        reason = 'UNKNOWN_PROVIDER_STATE'
    elif status in TERMINAL:
        reason = 'PROVIDER_TERMINAL'
    elif status != 'RUNNING':
        reason = 'WAIT_PROVIDER_RUNNING'
    elif direct is None:
        reason = 'WAIT_DIRECT_ENDPOINT'
    else:
        reason = 'READY' if valid else 'INVALID_DIRECT_ENDPOINT'
    return dict(row, readiness=reason)


SIGNALS = {
    'image_pull_error': r'(?:pull|manifest|image).*(?:error|fail|denied|not found)|failed to pull',
    'image_pull_progress': r'pulling|downloading|extracting|pull complete',
    'container_exit': r'container.*(?:exit|died|failed to start)',
    'address_in_use': r'address already in use|errno 98',
    'python_traceback': r'traceback \(most recent call last\)',
    'python_runtime_error': r'\b(?:FileExistsError|PermissionError|ModuleNotFoundError|SyntaxError|AssertionError|SSLError|TimeoutError)\b',
    'out_of_memory': r'out of memory|oomkilled',
    'gpu_runtime_error': r'cuda.*(?:error|fail)|nvidia.*(?:error|fail)',
}


def log_summary(raw):
    """SSE text is transient. Retain counts/signatures only, never log text."""
    signals, sources = {}, {}
    events = malformed = 0
    for line in raw.decode('utf-8', errors='replace').splitlines():
        if not line.startswith('data:'):
            continue
        try:
            event = json.loads(line[5:].strip())
            message = event['line']
            if not isinstance(message, str):
                raise ValueError('not a log line')
        except (ValueError, KeyError, TypeError):
            malformed += 1
            continue
        events += 1
        source = event.get('source')
        source = source if source in ('container', 'system') else 'unknown'
        sources[source] = sources.get(source, 0) + 1
        matched = False
        for name, pattern in SIGNALS.items():
            if re.search(pattern, message, re.IGNORECASE):
                signals[name] = signals.get(name, 0) + 1
                matched = True
        if not matched:
            signals['unclassified'] = signals.get('unclassified', 0) + 1
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
            'events': events, 'malformed_events': malformed, 'sources': sources,
            'signals': signals, 'raw_text_retained': False,
            'interpretation': 'Text signatures only; not a root-cause determination'}
