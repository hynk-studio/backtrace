"""Fixed 18-slot order and reserved teardown time; contains no provider API."""
import time
from tools import research_comparison as c


def sequence(execute, *, deadline, clock=time.monotonic):
    selection=c.parse((c.ROOT/'docs/research-selection-20261024.json').read_bytes())
    c.validate_selection(selection,c.load_protocol())
    rows=[]; blocked=False
    for task in selection['primary']:
        for arm in task['arm_order']:
            row={'instance_id':task['instance_id'],'arm':arm,'status':'NOT_RUN'}
            # 330 includes setup/cleanup. Agent work remains exactly 300.
            if blocked or deadline-clock() < 330+360+300:
                row['reason']='remaining full child plus export/deletion reserve unavailable'
                blocked=True
            else:
                try: row.update(execute(task['instance_id'],arm,330))
                except Exception as error:
                    row.update(status='INFRASTRUCTURE_FAILURE',error_type=type(error).__name__)
                    blocked=True
            rows.append(row)
    return {'planned_slots':18,'slots':rows,'all_slots_attempted':all(r['status']!='NOT_RUN' for r in rows),
            'effect_estimate':'NOT_COMPUTED','reserved_export_seconds':360,'reserved_cleanup_seconds':300}
