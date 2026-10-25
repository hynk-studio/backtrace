"""Single-slot official runner qualified only against authored CPU responses.

No provider/model startup or production launch CLI. A future paid integration
must enforce OS isolation, upstream access and the enclosing 330-second child
limit; the CPU harness invokes this same function in a bounded child process.
"""
import asyncio
import json
import os
from pathlib import Path
import time

from tools import research_comparison as c
from tools.research_assets import FIELDS, asset_paths
from tools.research_meter import Ledger, gateway
from tools.research_official import MODEL, MODEL_PATH, materialize_candidate


def checked_slot(inputs, identifier, arm):
    protocol = c.load_protocol()
    selection = c.parse((c.ROOT / 'docs/research-selection-20261024.json').read_bytes())
    c.validate_selection(selection, protocol)
    if arm not in c.ARMS or identifier not in {r['instance_id'] for r in selection['primary']}:
        raise ValueError('only preregistered primary slots allowed')
    lock = c.parse((c.ROOT / 'docs/research-assets-20261024.json').read_bytes())
    if lock['status'] != 'PASS' or lock['protocol_sha256'] != c.digest(c.encoded(protocol)):
        raise ValueError('completed matching asset lock required')
    rows = [r for r in lock['tasks'] if r['instance_id'] == identifier]
    if len(rows) != 1 or rows[0]['status'] != 'ACQUIRED' or rows[0]['failures']:
        raise ValueError('unavailable or ambiguous task assets')
    row = rows[0]
    task_data = c.read_file(inputs / 'agents' / identifier / 'agent-task.json', 1024**2)
    task = c.parse(task_data)
    if set(task) != set(FIELDS) or c.digest(task_data) != row['agent_task_sha256']:
        raise ValueError('agent-only task projection changed')
    selected = next(r for r in selection['primary'] if r['instance_id'] == identifier)
    if (task['repo'].lower() != selected['repo'] or task['base_commit'] != selected['base_commit']
            or task['instance_id'] != identifier):
        raise ValueError('selected task identity changed')
    if {r['path'] for r in row['assets']} != set(asset_paths(task)) or len(row['assets']) != 3:
        raise ValueError('task asset closure changed')
    for asset in row['assets']:
        data = c.read_file(inputs / 'assets' / asset['path'], asset['bytes'])
        if len(data) != asset['bytes'] or c.digest(data) != asset['sha256']:
            raise ValueError('task asset bytes changed')
    return task, row


def run_slot(inputs, output, identifier, arm, upstream_port, wheels, *, isolation=None, upstream=None,
             qualification_seconds=None):
    from adk_submission import VllmConfig, VllmServer, discover_adapters
    from google.adk.agents.context_cache_config import ContextCacheConfig
    from google.adk.apps._configs import EventsCompactionConfig
    from swegemma.config import EvalConfig
    from swegemma.models import Task
    from swegemma.context import SwegemmaContext
    from swegemma.sandbox import SubprocessManager
    from swegemma.deduplication import resolve_task_snapshot_paths
    from swegemma.harness.agent_runner import run_agent_sandbox
    from swegemma.harness.verification import save_trace_artifact
    import yaml
    inputs, output = Path(inputs).absolute(), Path(output).absolute()
    task_data, identity = checked_slot(inputs, identifier, arm)
    output.mkdir(mode=0o700)  # A new workspace is mandatory for every arm.
    (output / 'results').mkdir(mode=0o700)
    sample = output / 'candidate'
    expected = materialize_candidate(inputs / 'candidates' / (arm + '.zip'), arm, sample)
    task_path = output / 'agent-task.json'; c._new_output(task_path, c.encoded(task_data))
    task = Task(**task_data)
    if task.patch or task.test_patch or task.FAIL_TO_PASS or task.PASS_TO_PASS:
        raise ValueError('evaluator fields entered the agent')
    # Official perf_counter session boundary, including setup exclusion and the
    # exact start timestamp. No second timer begins at the first HTTP request.
    seconds = 300 if qualification_seconds is None else qualification_seconds
    if qualification_seconds is not None and (upstream is None or not 0 < seconds < 300):
        raise ValueError('scaled deadline is only for isolated authored split qualification')
    ledger = Ledger(MODEL_PATH, seconds=seconds, clock=time.perf_counter)
    class MeasuredContext(SwegemmaContext):
        def __setattr__(self, name, value):
            super().__setattr__(name, value)
            if name == 'patch_submitted' and value is True:
                # The original submit_patch first writes submitted_patch, then
                # this flag. Persist that exact artifact atomically before its
                # acknowledgement; an outer kill may prevent runner finalizers.
                patch = self.submitted_patch.encode()
                checkpoint = {'instance_id': identifier, 'arm': arm,
                    'source': 'ORIGINAL_SUBMIT_PATCH', 'patch': self.submitted_patch,
                    'bytes': len(patch), 'sha256': c.digest(patch), 'accounting': ledger.report(),
                    'namespace_ids': [] if isolation is None else
                        [n.namespace_id for n in isolation.namespaces.values()]}
                temporary = output/'submitted-checkpoint.partial'
                with temporary.open('wb') as stream:
                    os.fchmod(stream.fileno(), 0o600); stream.write(c.encoded(checkpoint))
                    stream.flush(); os.fsync(stream.fileno())
                os.replace(temporary, output/'submitted-checkpoint.json')
                descriptor = os.open(output, os.O_DIRECTORY)
                try: os.fsync(descriptor)
                finally: os.close(descriptor)
        def start_agent_session(self):
            super().start_agent_session()
            ledger.start(self.agent_start_time)
            if isolation is not None: isolation.begin(self.agent_start_time, seconds)
        def stop_agent_session(self):
            super().stop_agent_session()
            ledger.close()
            if isolation is not None: isolation.finish()
    manager = SubprocessManager(timeout_seconds=60, base_dir=output / 'sandboxes')
    if isolation is not None: isolation.attach(manager)
    server = None; begin = time.perf_counter()
    result = {'instance_id': identifier, 'arm': arm, 'candidate_sha256': expected['archive_sha256'],
              'agent_task_sha256': identity['agent_task_sha256'], 'status': 'INCOMPLETE',
              'verification': 'NOT RUN', 'upstream': 'CALLER_PROVIDED_LOOPBACK',
              'os_isolation': 'NOT QUALIFIED; CPU fixture only'}
    from tools.research_verifier_policy import identity as evaluation_identity
    result['evaluation_protocol'] = evaluation_identity()
    if upstream is not None:
        if isolation is None: raise ValueError('remote inference requires native CPU isolation')
        result['upstream'] = upstream.identity()
    try:
        with gateway(ledger, upstream_port, upstream=upstream) as port:
            adapters = discover_adapters(sample)
            server = VllmServer(VllmConfig(model=MODEL_PATH, port=port, tool_call_parser='gemma4',
                reasoning_parser='gemma4', default_chat_template_kwargs={'enable_thinking': True}),
                adapter_manifest=adapters)
            models = server.create_model_registry(aliases=[MODEL], model_prefix='openai/', api_key='EMPTY')
            raw = yaml.safe_load((sample / 'eval_config.yaml').read_text())['evaluation']
            if raw != {'timeout_seconds': 60, 'max_tool_calls': 30, 'max_time_minutes': 5, 'max_turns': 50}:
                raise ValueError('matched task allowance changed')
            config = EvalConfig(tasks_path=task_path, snapshots_dir=inputs / 'assets/snapshots',
                results_dir=output / 'results', submission_dir=sample, models=models,
                sandbox='subprocess', wheels_dir=Path(wheels), graph_dir=str(inputs / 'assets/graphs'),
                embeddings_dir=str(inputs / 'assets/embeddings'), adapter_manifest=adapters,
                context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
                events_compaction_config=EventsCompactionConfig(compaction_interval=15, overlap_size=2,
                    token_threshold=14336, event_retention_size=5), display_mode='quiet', **raw)
            context = MeasuredContext(task=task, task_id=identifier, repo=task.repo,
                graph_dir=config.graph_dir, embeddings_dir=config.embeddings_dir,
                budget=config.budget, harness=config.harness)
            snapshot, base, reconstruction = resolve_task_snapshot_paths(config.snapshots_dir, identifier, task.repo)
            patch, error, trace = asyncio.run(run_agent_sandbox(manager, config, task, snapshot,
                base_snapshot_path=base, patch_path=reconstruction, task_index=1, total_tasks=1, context=context))
            c._new_output(output / 'agent.patch', patch.encode())
            save_trace_artifact(trace, config.results_dir, identifier)
            result.update(status='COMPLETED' if not error and context.patch_submitted else 'INCOMPLETE',
                agent_error_type=None if not error else 'OFFICIAL_RUNNER_ERROR',
                patch_submitted=context.patch_submitted, patch_bytes=len(patch.encode()),
                patch_sha256=c.digest(patch.encode()), charged_tool_calls=context.tool_calls_used,
                official_llm_events=context.llm_calls_used, agent_work_seconds=context.agent_elapsed_seconds,
                cache={'context_min_tokens': 2048, 'context_ttl_seconds': 1800, 'context_cache_intervals': 10,
                       'compaction_interval': 15, 'server_prefix_cache': 'NOT MEASURED ON CPU FIXTURE'})
            result['unsubmitted_diff'] = ('NOT_APPLICABLE_SUBMITTED' if context.patch_submitted
                else 'UNAVAILABLE_AFTER_ISOLATION_STOP' if isolation is not None else 'OFFICIAL_FALLBACK')
            result['qualification_seconds'] = qualification_seconds
            if error:
                c._new_output(output / 'agent-error.txt', str(error).encode())
    finally:
        cleanup = time.perf_counter()
        try:
            manager.close()
            if isolation is not None:
                isolation.finish(); result['isolation'] = isolation.report()
                result['os_isolation'] = 'DEDICATED_UID_PID_AND_NETWORK_NAMESPACES'
                if isolation.expired: result['status'] = 'TIMEOUT'
            if server is not None:
                server.stop(); Path(server.log_path).unlink(missing_ok=True)
            result['sandbox_cleanup'] = not manager.sandboxes
        finally:
            ledger.close()
            result.update(accounting=ledger.report(), cleanup_seconds=time.perf_counter() - cleanup,
                          total_wall_seconds=time.perf_counter() - begin)
            c._new_output(output / 'slot-receipt.json', c.encoded(result))
    return result
