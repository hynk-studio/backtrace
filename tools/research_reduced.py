"""Prospective nine-slot amendment; original six-task selection stays intact."""
import time
from tools import research_comparison as c

AMENDMENT = c.ROOT/'docs/research-reduced9-amendment-20261026.json'
PINS = ('research-comparison-protocol.json', 'research-selection-20261024.json',
        'research-assets-20261024.json', 'research-verifier-amendment-20261025.json')


def expected():
    selection=c.parse((c.ROOT/'docs/research-selection-20261024.json').read_bytes())
    c.validate_selection(selection,c.load_protocol())
    tasks=[];seen=set()
    for task in selection['primary']:
        if task['repo'] in seen:continue
        seen.add(task['repo']);i=len(tasks);arms=['R0','R1','R2']
        tasks.append({k:task[k] for k in ('instance_id','repo','base_commit')} |
                     {'arm_order':arms[i:]+arms[:i]})
    if len(tasks)!=3:raise ValueError('original selection must contain exactly three repositories')
    return {'schema':1,'pilot':'R012-reduced9-v1','planned_slots':9,
        'selection_rule':'first original primary task per distinct repository, preserving repository order',
        'selection_uses_model_outcomes':False,'primary':tasks,
        'arm_order_rule':'cyclic Latin order; each arm occurs once in each position',
        'carryover_pair_balance':False,'task_replacement':False,
        'inherited_source_sha256':{n:c.digest((c.ROOT/'docs'/n).read_bytes()) for n in PINS},
        'allocations':1,'automatic_paid_retry':False,'total_seconds':7740,
        'setup_seconds':4020,'child_seconds':330,'parent_seconds':10,
        'export_seconds':360,'cleanup_seconds':300,
        'maximum_additional_spend':'4.30','maximum_hourly_all_in':'2.00',
        'maximum_cumulative_spend':'9.50','credited_funding':'10.00',
        'prior_spend_floor':'5.0062308114','credit_reserve':'0.50','top_up_allowed':False,
        'evaluator':'unchanged v3 version-skip rules, reported separately from original official verdict',
        'evaluation_order':'independent CPU evaluation only after both owner and watcher confirm deletion',
        'missing_results':'retain all nine denominators; no effect estimate when incomplete',
        'R3':'separate; no dependency on a positive R2 result'}


def load():
    value=c.parse(AMENDMENT.read_bytes())
    if value!=expected():raise ValueError('reduced scope differs from prospective fixed amendment')
    return value


def identity():
    value=load()
    return {'pilot':value['pilot'],'planned_slots':9,'amendment_sha256':c.digest(AMENDMENT.read_bytes()),
            'raw_runner_identity':'inherited original v3 rules; its 18-slot metadata is historical'}


def sequence(execute, *, deadline, clock=time.monotonic):
    policy=load();rows=[];blocked=False
    for task in policy['primary']:
        for arm in task['arm_order']:
            row={'instance_id':task['instance_id'],'arm':arm,'status':'NOT_RUN'}
            reserve=sum(policy[k] for k in ('child_seconds','parent_seconds','export_seconds','cleanup_seconds'))
            if blocked or deadline-clock()<reserve:
                row['reason']='remaining full child, parent teardown and export/deletion reserve unavailable'
                blocked=True
            else:
                try:row.update(execute(task['instance_id'],arm,policy['child_seconds']))
                except Exception as error:
                    row.update(status='INFRASTRUCTURE_FAILURE',error_type=type(error).__name__);blocked=True
            rows.append(row)
    return {'pilot_scope':identity(),'planned_slots':9,'slots':rows,
        'all_slots_attempted':all(r['status']!='NOT_RUN' for r in rows),
        'effect_estimate':'NOT_COMPUTED','reserved_parent_teardown_seconds':10,
        'reserved_export_seconds':360,'reserved_cleanup_seconds':300}
