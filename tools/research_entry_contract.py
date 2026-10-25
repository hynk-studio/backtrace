"""One proposed 18-slot scope. A proposal is never a paid authorization."""
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
import time

from tools import runpod_control as control

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'hynk-studio/backtrace'
REVIEW = 'bt-001-research-prepaid-entry-20261026'
OWNER = 'bt-001-research-start-20261026'
WATCH = 'bt-001-research-watch-20261026'
STATE = 'bt-001-research-state-20261026'
PAID_NAMESPACE = 'pilot-20261026'
CONTRACT = {'schema': 1, 'pilot': 'R012-matched-pilot-v3-version-skip',
    'slots': 18, 'allocations': 1, 'servers': 1, 'automatic_retry': False,
    'total_seconds': 10800, 'setup_seconds': 4020, 'export_seconds': 360,
    'cleanup_seconds': 300, 'child_seconds': 330, 'parent_seconds': 10,
    'maximum_additional_spend': '6.00', 'maximum_hourly': '2.00',
    'maximum_proposed_cumulative': '12.00', 'credit_reserve': '0.50',
    'hardware': control.GPU, 'image': control.BASE, 'disk_gb': 100,
    'transport': 'pinned SSH22 delivery plus provider-mapped mutually pinned TLS8443'}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else encoded(value)).hexdigest()


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('finite number required')
    return value


def traversable_directory(path):
    """Permit path traversal under a private umask; files keep their own modes."""
    path=Path(path);path.mkdir(mode=0o711);path.chmod(0o711);return path


def source_files():
    paths = list(ROOT.glob('tools/*.py')) + list(ROOT.glob('tests/*.py'))
    paths += list((ROOT/'.github/workflows').glob('research-entry*.yml'))
    paths += [ROOT/'docs'/n for n in ('research-comparison-protocol.json',
        'research-selection-20261024.json', 'research-assets-20261024.json',
        'research-verifier-amendment-20261025.json', 'linux-wheel-manifest.json')]
    return {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in sorted(paths)}


def permit(value, source_sha, now, *, replica=False):
    if not isinstance(value, dict) or set(value) != {'id', 'source_sha', 'contract_sha256',
            'qualification_run_id', 'approved_at', 'expires_at', 'additional_cap',
            'cumulative_cap', 'account_funded_total', 'prior_spend_floor', 'single_use', 'mode'}:
        raise ValueError('fresh explicit authorization required')
    if (value['mode'] != ('CPU_REPLICA' if replica else 'OWNER_APPROVED_PAID')
            or value['single_use'] is not True or value['source_sha'] != source_sha
            or not re.fullmatch('[0-9a-f]{40}', source_sha)
            or value['contract_sha256'] != digest(CONTRACT)
            or not re.fullmatch('[a-z0-9-]{8,100}', value['id'])
            or not re.fullmatch('[1-9][0-9]{0,19}', str(value['qualification_run_id']))
            or not number(value['approved_at']) <= now < number(value['expires_at'])
            or value['expires_at']-value['approved_at'] > 86400):
        raise ValueError('authorization source, mode or validity mismatch')
    if not (0 < control.money(value['additional_cap']) <= Decimal('6')
            and 0 < control.money(value['cumulative_cap']) <= Decimal('12')
            and Decimal('10') <= control.money(value['account_funded_total']) <= Decimal('16.50')
            and control.money(value['prior_spend_floor'])<=control.money(value['account_funded_total'])):
        raise ValueError('explicit finite spend limits required')
    return value


def costs(offer, authorization, now, *, seconds=10800):
    exact = {'gpu': control.GPU, 'gpu_count': 1, 'cloud': 'SECURE',
        'image': control.BASE, 'container_disk_gb': 100, 'volume_gb': 0,
        'network_volume': None, 'interruptible': False, 'stock_available': True,
        'auto_pay': False, 'authenticated': True}
    if any(type(offer.get(k)) is not type(v) or offer.get(k) != v for k,v in exact.items()):
        raise ValueError('exact offer required')
    control.validate_region(offer['region'])
    if (not 0 <= now-control.timestamp(offer['observed_at']) <= 300
            or type(offer['vcpus']) is not int or offer['vcpus'] < 8
            or type(offer['ram_gb']) is not int or offer['ram_gb'] < 117):
        raise ValueError('stale offer or hardware mismatch')
    compute, storage, tax, fixed, balance = [control.money(offer[k]) for k in
        ('compute_per_hour','storage_per_hour','tax_rate','other_total','credit_balance')]
    hourly = (compute+storage)*(1+tax)
    # Funding and previously observed spend must be explicitly reviewed. A
    # top-up must never make historical spending disappear from the calculation.
    funded=control.money(authorization['account_funded_total'])
    spent=funded-balance
    if (balance>funded or spent<control.money(authorization['prior_spend_floor'])
            or fixed != 0 or not 0 < hourly <= 2 or not 0 < seconds <= 10800):
        raise ValueError('unreviewed charges, account basis or hourly limit')
    maximum = hourly*Decimal(str(seconds))/3600
    if (maximum > control.money(authorization['additional_cap'])
            or maximum+spent > control.money(authorization['cumulative_cap'])
            or maximum+Decimal('.50') > balance):
        raise ValueError('credit or approved cumulative/additional cap insufficient')
    return {'hourly_all_in':str(hourly),'maximum_all_in':str(maximum),
        'compute_per_hour':str(compute),'storage_per_hour':str(storage),
        'tax_rate':str(tax),'other_total':'0','spent_before':str(spent),
        'initial_balance':str(balance),'funded_total':str(funded), 'additional_cap':authorization['additional_cap'],
        'cumulative_cap':authorization['cumulative_cap']}


def require_run(value, run_id, source, branch, *, path=None):
    if (str(value.get('id')) != str(run_id) or value.get('head_sha') != source
            or value.get('head_branch') != branch or value.get('run_attempt') != 1
            or value.get('status') != 'in_progress' or value.get('event') != 'push'
            or (path and value.get('path') != path)):
        raise ValueError('first exact independent workflow run required')


def resource_matches(pod, claim):
    if not isinstance(pod, dict) or sorted(pod.get('ports', [])) != ['22/tcp','8443/tcp']:
        return False
    return control.resource_matches(dict(pod, ports=['22/tcp']), {
        'request':{'name':claim['name']},'region':claim['region'],'costs':claim['costs']})


def endpoints(pod):
    from tools.ssh_bootstrap import validate_endpoint
    direct=pod['ssh']['direct']
    if direct['username']!='root':raise ValueError('root SSH endpoint required')
    validate_endpoint(direct['host'],direct['port'])
    rows=pod['runtime']['ports'];matched={}
    for port in (22,8443):
        found=[r for r in rows if r.get('private')==port and r.get('type')=='tcp']
        if len(found)!=1:raise ValueError('exact provider port mapping required')
        row=found[0];validate_endpoint(row['ip'],row['public'])
        matched[port]={'host':row['ip'],'port':row['public']}
    if matched[22]!={'host':direct['host'],'port':direct['port']}:
        raise ValueError('SSH mapping contradicts direct endpoint')
    if matched[8443]['host']!=direct['host'] or matched[8443]['port']==direct['port']:
        raise ValueError('distinct TLS port on the same observed host required')
    return {'ssh':direct,'tls':matched[8443]}


def qualification(store, authorization):
    run = store.run(authorization['qualification_run_id'])
    if (run.get('head_sha') != authorization['source_sha'] or run.get('head_branch') != REVIEW
            or run.get('run_attempt') != 1 or run.get('status') != 'completed'
            or run.get('conclusion') != 'success' or run.get('event') != 'push'
            or run.get('path') != '.github/workflows/research-entry-cpu.yml'):
        raise ValueError('successful exact-source full free qualification required')


def budget_reason(claim, phase, now):
    elapsed = number(now)-claim['requested_at']
    if elapsed < 0: return 'CLOCK_REVERSED'
    if elapsed >= claim['total_seconds']-claim['cleanup_seconds']: return 'CLEANUP_RESERVE'
    if phase == 'setup' and elapsed >= claim['setup_seconds']: return 'SETUP_DEADLINE'
    cost = control.money(claim['costs']['hourly_all_in'])*Decimal(str(elapsed+claim['cleanup_seconds']))/3600
    if (cost > control.money(claim['costs']['additional_cap']) or
            cost+control.money(claim['costs']['spent_before']) > control.money(claim['costs']['cumulative_cap'])):
        return 'PROJECTED_COST'
    return None
