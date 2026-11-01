"""Bounded error evidence around the immutable historical provider client."""
import hashlib
import json
import re
import urllib.error
from tools import runpod_control as control


def provider_problem(error, key, request_body):
    """Bound and redact RFC-style problem fields; never retain a raw body."""
    result = {'schema': 'redacted_provider_problem_v1'}
    try:
        raw = error.read(8193)
    except Exception:
        return dict(result, body_read='UNAVAILABLE')
    finally:
        try: error.close()
        except Exception: pass
    if not isinstance(raw, bytes): return dict(result, body_read='UNAVAILABLE')
    result.update(observed_bytes=len(raw), prefix_sha256=hashlib.sha256(raw).hexdigest(),
                  truncated=len(raw) > 8192)
    if result['truncated']: return dict(result, body_format='TOO_LARGE')
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError):
        return dict(result, body_format='NOT_JSON')
    if not isinstance(value, dict): return dict(result, body_format='NOT_OBJECT')
    secrets = {key}
    def collect(item):
        if isinstance(item, dict):
            for child in item.values(): collect(child)
        elif isinstance(item, (list, tuple)):
            for child in item: collect(child)
        elif isinstance(item, str) and item:
            secrets.add(item)
    collect(request_body)
    redaction = re.compile('|'.join(re.escape(s) for s in sorted(secrets, key=len, reverse=True)))
    def clean(text):
        if not isinstance(text, str): return None
        # Request echoes, credentials and PEM material are not useful public
        # diagnostics. Keep their response fingerprint, not their content.
        if re.search(r'authorization|bearer\s|private.key|ssh-rsa|ssh-ed25519|'
                     r'-----BEGIN|password|secret|token|api.?key|entrypoint|docker|'
                     r'\b(?:env|args|cmd)\b|[{}\[\]]', text, re.I):
            return '[REDACTED_SENSITIVE_DETAIL]'
        # One pass prevents short values from expanding previously inserted
        # redaction markers and bounds work by the original response text.
        text = redaction.sub('[REDACTED]', text)
        text = re.sub(r'https?://\S+', '[REDACTED_URL]', text)
        text = re.sub(r'[A-Za-z0-9_+/=-]{24,}', '[REDACTED_IDENTIFIER]', text)
        return ' '.join(text.split())[:400]
    result['body_format'] = 'JSON_OBJECT'
    for name in ('title', 'detail'):
        text = clean(value.get(name))
        if text is not None: result[name] = text
    if type(value.get('status')) is int and value['status'] == error.code:
        result['status'] = value['status']
    if isinstance(value.get('errors'), list):
        result['errors'] = [clean(v) for v in value['errors'][:3] if isinstance(v, str)]
    return result



class RunpodAPI(control.RunpodAPI):
    """Synchronous controller client; delegate wire behavior to the frozen base."""
    def request(self, method, path, body=None, missing=False):
        original = self._open
        captured = []
        def observe(request, timeout):
            try:
                return original(request, timeout=timeout)
            except urllib.error.HTTPError as error:
                if not (missing and error.code == 404):
                    captured.append(provider_problem(error, self._key, body))
                raise
        self._open = observe
        try:
            return super().request(method, path, body=body, missing=missing)
        except control.ProviderError as error:
            if captured: error.problem = captured[-1]
            raise
        finally:
            self._open = original
