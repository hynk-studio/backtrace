# Proposed single public task smoke — NOT RUN

This is a preparation recipe for a separately authorized run, not permission to
download the model, allocate a GPU or execute a notebook. Use the existing private
Kaggle path first. The owner has already entered; no repeat enrollment or manual
desktop preparation is needed. This slice acquired no model or task data.

## Frozen inputs and selection

- Candidate: the six-file R0-clean archive, **6,230 bytes**, SHA-256
  `2e24495826cb971053439a00d9ad8350471fc0efffa41a54b82082feedaa7358`.
  Materialize its already-inspected bytes privately; do not rebuild or resample.
- Recipe: organizer notebook **135692529 v2**, SHA-256
  `0c54c3bac3269e422b1d48ac8087ff26b49fe764231b7983c90ef842382f9a87`.
  Image recorded there: `gcr.io/kaggle-private-byod/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461`.
- Official packages: swegemma **0.2.7**, adk-submission **0.2.11**,
  adk-eval-core **0.1.0**, google-adk **1.36.1**, google-genai **2.11.0**;
  retain [the acquired hashes](source-manifest.json). Full Linux/vLLM/CUDA/torch
  environment pins still need recording; the macOS CPU lock is not that environment.
- Model: `google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2`, mounted at
  `/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2`.
  Refuse helper version-1 defaults and fallback search. Before startup, record
  actual file sizes/hashes, weight index/shards, config/quantization metadata,
  tokenizer files and chat template, and any upstream revision actually present.
  Those immutable bytes/revision and runtime compatibility are **not acquired or
  verified yet**. No adapter is selected; inference weights are not a training claim.
- Precommitted task rule: choose the **lexicographically smallest distinct public
  development `instance_id`** from the pinned public `tasks.jsonl` metadata,
  before inspecting any reference patch or test outcome. Reject conflicting
  duplicate IDs. Freeze the chosen ID, metadata source/hash and selection receipt;
  never choose a replacement because the task fails. **ID unresolved:** the public
  ID/repo/base-commit index has not been acquired. Do not invent an ID.

Acquire only that task's public issue/repo/base-commit/hints, its snapshot closure,
matching graph JSON/embedding NPZ and offline task dependency wheels. Official
`resolve_task_snapshot_paths` supports `snapshots/fallbacks/<id>.tgz`, or a
`base_snapshots/base_<sanitized_repo>.tgz` plus `patches/<id>.patch`, or a direct
`<id>.tgz`/`.tar.gz`. The reconstruction patch is not the gold solution. Resolve
the actual path using the selected metadata and pin every input before startup.
Graph/embedding lookup uses repo/base-commit identifiers; inspect the exact
resolved files rather than acquiring all graphs or snapshots. Missing inputs end
the attempt; they do not authorize bulk download or a different task.

Keep the public `patch`, `test_patch`, `FAIL_TO_PASS` and `PASS_TO_PASS` outside
the agent process and its readable mounts. No hidden cases/labels/secret bundle
are needed. `SubprocessManager` is not an OS filesystem security boundary: simply
omitting answer fields from the prompt while mounting the full competition data
is insufficient. Prepare a private minimal agent-input bundle with **only** the
selected public task's allowed fields and dependencies. Keep the evaluation-only
record in separate storage until the agent process and its children are stopped.
If that separation cannot be established on Kaggle, stop before allocation.
Rights/public-sharing uncertainty in [the contract](competition-contract.md)
remains; do not publish this bundle, notebook inputs or outputs.

## Resource evidence and finite envelope

Observed 2026-09-29 around **02:28 UTC**, through existing authorized Kaggle UI:
[settings](https://www.kaggle.com/settings) showed GPU usage **00:00 / 30 hours**.
The private new-notebook accelerator selector offered **None, GPU T4 x2,
TPU v5e-8**; L4 x4 was absent. Inspection left None selected and the draft session
off, with no input/cell execution or saved published version. It created an empty
private draft only. Evidence: rendered primary UI/observed interaction, no retained
page bytes, SHA-256 **null**; quota and options must be rechecked before use.
This is an offered option, not an allocated or tested machine.

Proposed run name: **R0-clean-v2-one-public-task/T4x2**. Hardware differs from the
organizer's published L4 x4 run. Preserve the notebook's adaptive TP/dtype rule:
on two GPUs TP=2; dtype is bfloat16 only if supported, otherwise `auto`.
T4 has 16 GB/device ([NVIDIA specifications](https://www.nvidia.com/en-gb/data-center/tesla-t4/));
32 GB aggregate is not one pooled allocation or evidence the 32768-context QAT
checkpoint fits. Actual required VRAM, kernels, tokenizer/template behavior and
startup time are unknown. A startup failure/OOM is a result; no quantization,
context-length, dtype or budget workaround is authorized by this recipe.

| Bound | Proposed limit |
| --- | --- |
| Total allocation wall time | **1,800 seconds**, including setup, startup, task, optional verification and cleanup; stop useful work by 1,740 seconds. |
| Setup / startup | Setup at most 300 seconds; server startup at most **1,200 seconds**, also bounded by remaining total time. One server start. |
| Agent / commands | **1 minute**, **10 tool calls**, **50 turns**, **60 seconds per command**, exactly from frozen eval_config. Setup is outside the official agent timer, inside the total cap. |
| Retry | No rerun of task/server or automatic hardware fallback. Retain official ModelRetryPlugin defaults: at most 5 retries per transient failure, initial 3 seconds, exponential factor 2, 60-second delay ceiling with jitter. All attempts/time count; record actual HTTP attempts as well as ADK turns since plugin retries need not increment that counter. |
| GPU use / spend | T4 x2: at most **1 aggregate GPU-hour**; free quota only, **$0 paid spend**. No paid overflow. |
| Storage | Require a metadata-based fit check before allocation: at most 40 GiB read-only selected assets, 20 GiB writable scratch, 1 GiB private receipts. These are proposed ceilings, not measured asset requirements or verified Kaggle capacity. Fail if unavailable/insufficient. |
| Cleanup | Stop server and descendants, close sandbox manager, remove temporary repositories/caches; confirm session stopped and quota clock no longer advancing. Retain only private hashes, redacted trace, generated patch and result. Never publish raw task/answer content. |

If T4 x2 cannot support the unchanged recipe, the **alternative requiring a new
paid authorization** is one `g2-standard-48` VM (4 L4, 96 GB aggregate VRAM), the
same 30-minute ceiling (at most **2 GPU-hours**), a 100 GiB auto-deleting balanced
disk, and a **$10 all-in hard ceiling** including disk/egress. This is a cap, not a
price estimate or a reservation. Obtain a region-specific quote and confirm
independent expiry/VM+disk deletion before creation; reject a quote above the cap.
Use a pinned compatible Linux image; do not silently claim Kaggle-image parity.
This alternative is named **R0-clean-v2-one-public-task/L4x4-rental** and is never
an automatic second attempt. [Google's machine table](https://docs.cloud.google.com/compute/docs/accelerator-optimized-machines#g2-vms)
supports the machine/GPU count, not model fit or availability. NVIDIA and Google
primary pages were read on 2026-09-29 around 02:50 UTC; no downloaded byte snapshot
or version ID, SHA-256 **null**. Search snippets were only discovery aids.

## Exact notebook patch to prepare privately after authorization

Use the pinned v2 source, not the current mutable web notebook. Keep a private
diff and hashes of the generated execution script. This proposed patch has **not
been executed**; it is not a second packaging or orchestration framework.

1. Retain cell `e368fd3b`'s offline environment/dependency setup only against the
   verified image/wheels; record the actual Linux lock before model startup. Do
   not run examples or install an unpinned replacement to fix compatibility.
2. Replace cell `63cb4756`'s full data mount, starter copy and sampling rewrite
   with the verified six-file materialized candidate at `AGENT_DIR`. Point
   `DATA_DIR` at the private minimal bundle; `TASKS_PATH = DATA_DIR / 'agent-task.json'`.
   It contains one object, selected by the rule above, with exactly `instance_id`,
   `repo`, `base_commit`, `problem_statement`, `hints_text`. Set `GRAPH_DIR` and
   `EMBEDDINGS_DIR` to that bundle's selected directories. Omit graph-demo cell
   `9280c4a8`; there is no warm-up model request.
3. Retain cell `f0b1ab0d`'s explicit version-2 model path and server configuration:
   localhost:8000, gemma4 tool/reasoning parsers, max_model_len 32768, GPU fraction
   0.90, auto tool choice, enable_lora=True, max_loras=8, max_lora_rank=128. Empty
   adapter discovery means no adapter loading despite the retained capability
   flag. Keep `litellm.drop_params=True` and the existing sampling; whether the
   4096 thinking budget is honored on the wire is still unverified. Wrap startup
   and the task in `try/finally: server_instance.stop()`; no Transformers fallback.
4. In `105c5b68`, retain the entire `EvalConfig` construction, including caching
   (2048/1800/10) and compaction (15/2/14336/5). Assert the four frozen budgets.
   Replace the `tasks[:2]`, `Evaluator`, loop and submission DataFrame with the
   following **one** agent call. This named driver deviation, **public-input
   separation**, invokes the same official phase-1 function without Evaluator's
   secret hydration/fallback; it adds no prompt or agent intervention.

```python
# Proposed replacement after eval_config construction; NOT EXECUTED here.
import json
from swegemma.models import Task
from swegemma.context import SwegemmaContext
from swegemma.sandbox import SubprocessManager
from swegemma.deduplication import resolve_task_snapshot_paths
from swegemma.harness.agent_runner import run_agent_sandbox
from swegemma.harness.verification import save_trace_artifact

fields = {'instance_id', 'repo', 'base_commit', 'problem_statement', 'hints_text'}
record = json.loads(TASKS_PATH.read_text())
assert set(record) == fields
task = Task(**record)  # all evaluator-only Task fields retain empty defaults
assert (timeout_seconds, max_tool_calls, max_time_minutes, max_turns) == (60, 10, 1, 50)
snapshot, base_snapshot, reconstruction = resolve_task_snapshot_paths(
    eval_config.snapshots_dir, task.instance_id, task.repo)
assert snapshot.is_file()
manager = SubprocessManager(timeout_seconds=60, base_dir=WORKING_DIR / 'sandboxes')
context = SwegemmaContext(task=task, task_id=task.instance_id, repo=task.repo,
    problem_statement=task.problem_statement, hints_text=task.hints_text,
    graph_dir=GRAPH_DIR, embeddings_dir=EMBEDDINGS_DIR,
    budget=eval_config.budget, harness=eval_config.harness)
try:
    patch, error, trace = run_sync(run_agent_sandbox, manager, eval_config, task,
        snapshot, base_snapshot_path=base_snapshot, patch_path=reconstruction,
        task_index=1, total_tasks=1, context=context)
    (WORKING_DIR / 'agent.patch').write_text(patch)
    save_trace_artifact(trace, eval_config.results_dir, task.instance_id)
    (WORKING_DIR / 'smoke.json').write_text(json.dumps({
        'instance_id': task.instance_id, 'agent_error': error,
        'tool_calls': context.tool_calls_used, 'llm_calls': context.llm_calls_used,
        'verification': 'NOT RUN in the agent process'}))
finally:
    manager.close()
    server_instance.stop()
```

5. Omit cell `d811048f`'s packaging/submission output. Run the privately prepared
   script once under a Linux process-group watchdog, for example
   `timeout --signal=TERM --kill-after=10s "$REMAINING_WORK_SECONDS" python -u one-task.py`,
   where the supervisor derives remaining seconds from allocation start and
   reserves 60 seconds for cleanup. Enforce the independent 1,800-second session
   stop even if Python or the notebook disconnects; a kernel timer alone does not
   stop GPU billing. Confirm no detached server children survive. If this stop
   mechanism cannot be established autonomously, do not start the session.

After the agent process/children are stopped, a separate CPU-only verification
phase may receive the selected **public** test record and `agent.patch`. Call
official `swegemma.harness.verification.verify_task(manager, eval_config,
public_task, snapshot, base_snapshot_path=base_snapshot,
patch_path=reconstruction, agent_patch=patch, fast_path=True)` with a fresh
SubprocessManager and the same snapshot, then `manager.close()` in `finally`.
Allow at most 180 seconds and only the remaining total time. Never call the
full Evaluator to fill missing answers. Keep the gold solution `patch` empty;
only public `test_patch`/test node lists go to this verifier. If the public test
record/dependencies or time are unavailable, record verification **NOT RUN**;
no hidden answer fallback, new GPU session or unbounded retry.

Required receipts distinguish server health, an actual returned model request,
tool events, generated patch hash (including an empty patch), timeout/error and
public test exit/resolved result when run. Reaching schema/compilation/health is
not task completion. Capture actual startup/task/total duration, peak GPU memory
and all inference attempts. One task is a smoke result, not a performance or
transfer estimate. Next authorization would cover exactly this bounded attempt
and necessary selected inputs; resource compatibility and stop controls remain
prerequisites, not enrollment work for the owner.
