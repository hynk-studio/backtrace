"""Actual frozen CPU verifier and graph query replay; no model/agent entry."""
import ast
import json
import os
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(root, inputs):
    from tools.runpod_job import check_owner_host
    from tools.recovered_task import analyze
    from tools.qualify_evaluation import qualify, diagnose_incomplete_receipts
    from tools.task_budget import PROPOSAL, check
    from swegemma.context import SwegemmaContext
    from swegemma.models import Task
    from swegemma.tools.graph import search_similar_code
    from swegemma import graph as graph_api
    import numpy as np
    import yaml
    check_owner_host()
    if any(k in os.environ for k in ('GITHUB_TOKEN', 'KAGGLE_API_TOKEN', 'RUNPOD_API_KEY')):
        raise ValueError('CPU analysis inherited a service credential')
    manifest = json.loads((ROOT / 'docs/task-followup-input-20261023.json').read_text())
    report = {'gpu_allocations': 0, 'model_calls': 0, 'agent_runs': 0,
              'analysis': analyze(root / 'receipts', manifest)}
    # Every query uses only the original agent-visible task and graph, never
    # the evaluator specification or its reference patch.
    task = Task(**json.loads((inputs / 'agent-task.json').read_text()))
    context = SwegemmaContext(task=task, repo=task.repo,
        graph_dir=str(inputs / 'graphs'), embeddings_dir=str(inputs / 'embeddings'),
        max_tool_calls=30, max_time_minutes=5)
    graph = graph_api.get_graph(task.repo, base_commit=task.base_commit,
        graph_dir=context.graph_dir, embeddings_dir=context.embeddings_dir)
    queries = [x['query'] for x in report['analysis']['trace_tool_events'] if 'query' in x]
    rows = []
    for query in queries:
        original = json.loads(search_similar_code(context, query))
        normalized = json.loads(search_similar_code(context, query.removeprefix('def ')))
        if original.get('status') != 'ok' or normalized.get('status') != 'ok':
            raise ValueError('actual graph tool failed')
        rows.append({'query': query, 'original_count': original['count'],
                     'function_name_count': normalized['count']})
    # A graph node need not have a stored vector. Match the already qualified
    # original-tool positive control: select an actual NPZ embedding key.
    with np.load(next((inputs / 'embeddings').glob('*.npz')), allow_pickle=False) as vectors:
        node = vectors.files[0]
    positive = json.loads(search_similar_code(context, node, k=1))
    if positive.get('status') != 'ok' or positive['count'] != 1:
        raise ValueError('known-node CPU graph positive control failed')
    report['graph_replay'] = {'queries': rows, 'known_node_control_count': positive['count'],
                              'tool_executions': context.tool_calls_used,
                              'model_calls': 0, 'harness_modified': False}
    with zipfile.ZipFile(inputs / 'r0-clean.zip') as archive:
        budget = yaml.safe_load(archive.read('eval_config.yaml'))['evaluation']
    retained = (root / 'retained-driver.py').read_text()
    tree = ast.parse(retained)
    phase = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'server_phase')
    timeouts = [n.value for n in ast.walk(phase) if isinstance(n, ast.keyword)
                and n.arg == 'timeout' and isinstance(n.value, ast.Constant)]
    child = [n.value for n in timeouts if n.value == 180]
    if len(child) != 1:
        raise ValueError('frozen agent child timeout shape changed')
    bad = dict(PROPOSAL, agent_child_seconds=child[0])
    report['budget_review'] = {'original_candidate': budget, 'original_agent_child_seconds': child[0],
        'unchanged_child_with_longer_session': check(bad, 5800, 6100),
        'proposal': PROPOSAL, 'proposal_checks': check(PROPOSAL, 5800, 6100),
        'late_setup_checks': check(PROPOSAL, 1500, 1800),
        'activation': 'NOT ACTIVATED; all scientific comparisons must use one matched budget'}
    # Only after the graph diagnostic is complete, run evaluator-only tests
    # under UID 65533. No model or agent can read these specifications.
    empty = root / 'empty.patch'; empty.write_text('')
    report['verifier_controls'] = qualify(root / 'evaluator/tasks.jsonl', inputs,
                                         empty, root / 'verifier-controls')
    report['partial_patch_verification'] = diagnose_incomplete_receipts(
        root / 'evaluator/tasks.jsonl', inputs, root / 'receipts', root / 'partial-verification', manifest)
    report['status'] = 'PASS'
    (root / 'followup-result.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    return report


if __name__ == '__main__':
    print(json.dumps(run(Path(sys.argv[1]), Path(sys.argv[2])), sort_keys=True))
