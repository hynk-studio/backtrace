"""Project declared URL lifetime without publishing URLs or authentication data.

Google Cloud Storage V4: X-Goog-Date + X-Goog-Expires; legacy V2: Expires.
These are declarations, not signature verification or future availability.
"""
from collections import Counter
from datetime import datetime, timezone
import re
import time
from urllib.parse import parse_qs, urlsplit

from tools.direct_delivery import validate_url


def expiry(url):
    validate_url(url)
    parsed = urlsplit(url)
    query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=128)
    def one(key):
        values = query.get(key)
        if values is None or len(values) != 1: raise ValueError('ambiguous declared expiry')
        return values[0]
    try:
        if 'X-Goog-Date' in query or 'X-Goog-Expires' in query:
            date, seconds = one('X-Goog-Date'), one('X-Goog-Expires')
            if not re.fullmatch(r'\d{8}T\d{6}Z', date) or not re.fullmatch(r'\d{1,6}', seconds):
                raise ValueError('invalid declared V4 expiry')
            duration = int(seconds)
            if not 0 < duration <= 604800: raise ValueError('invalid declared V4 duration')
            start = datetime.strptime(date, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).timestamp()
            return 'GCS_V4', start + duration
        if 'Expires' in query:
            seconds = one('Expires')
            if not re.fullmatch(r'\d{1,12}', seconds): raise ValueError('invalid declared V2 expiry')
            return 'GCS_V2', int(seconds)
    except (ValueError, OverflowError):
        return 'UNVERIFIABLE', None
    if not parsed.query and parsed.hostname in ('files.pythonhosted.org', 'download-r2.pytorch.org'):
        return 'PUBLIC_NO_DECLARED_EXPIRY', None
    return 'UNVERIFIABLE', None


def snapshot(streams, *, now=None, setup_seconds=5400):
    observed = time.time() if now is None else now
    result = {'observed_at_epoch': int(observed), 'required_setup_window_seconds': setup_seconds,
              'interpretation': 'Declared lifetime only; no URL/signature is published', 'streams': {}}
    for kind, sources in streams.items():
        types = Counter(); remaining = []
        for source in sources.values():
            name, deadline = expiry(source['url']); types[name] += 1
            if deadline is not None: remaining.append(int(deadline - observed))
        result['streams'][kind] = {'files': len(sources), 'formats': dict(types),
            'minimum_declared_remaining_seconds': min(remaining) if remaining else None,
            'expired': sum(value <= 0 for value in remaining),
            'shorter_than_setup_window': sum(value < setup_seconds for value in remaining),
            'unverifiable': types['UNVERIFIABLE']}
    return result
