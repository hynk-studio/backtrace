"""Select the frozen public smoke task in the preparation process, never the agent."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


def select_task(data):
    """Compare IDs/duplicate records without interpreting reference answers."""
    records = {}
    try:
        for line in data.splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError('task record must be an object')
            identifier = record.get('instance_id')
            if not isinstance(identifier, str) or not identifier.strip():
                raise ValueError('task record needs a nonempty instance_id')
            if identifier in records and records[identifier] != record:
                raise ValueError('conflicting duplicate instance_id')
            records[identifier] = record
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError('invalid public task JSONL') from None
    if not records:
        raise ValueError('public task metadata is empty')

    identifier = min(records)
    record = records[identifier]
    fields = ('instance_id', 'repo', 'base_commit', 'problem_statement', 'hints_text')
    # hints_text alone has an empty default in the pinned official Task class.
    task = {key: record.get(key, '' if key == 'hints_text' else None) for key in fields}
    if any(not isinstance(value, str) for value in task.values()):
        raise ValueError('selected task is missing a required string field')
    receipt = {
        'metadata_sha256': hashlib.sha256(data).hexdigest(),
        'metadata_bytes': len(data),
        'distinct_ids': len(records),
        'selected_instance_id': identifier,
        'selection_rule': 'lexicographically smallest distinct public instance_id',
    }
    return task, receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('metadata', type=Path)
    parser.add_argument('output', type=Path, help='new private agent-task.json; never overwritten')
    args = parser.parse_args(argv)
    created = False
    try:
        task, receipt = select_task(args.metadata.read_bytes())
        data = (json.dumps(task, sort_keys=True) + '\n').encode('utf-8')
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, 'wb') as output:
            output.write(data)
        receipt['agent_task_sha256'] = hashlib.sha256(data).hexdigest()
    except (OSError, ValueError) as error:
        if created:
            args.output.unlink(missing_ok=True)
        # Never echo task contents, reference fields or exception arguments.
        print('smoke selection failed: ' + (
            str(error) if isinstance(error, ValueError) else type(error).__name__), file=sys.stderr)
        return 2
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
