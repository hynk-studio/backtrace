# A matched R0/R1/R2 pilot prepared on CPU

Status: **CPU research preparation, no model run or paid authorization.**
The protocol is `R012-matched-pilot-v2` in
[research-comparison-protocol.json](research-comparison-protocol.json). It freezes
the successful runtime separately from the new scientific prompt comparison.
This is a six-task feasibility pilot, with one stochastic run per arm and task.
It cannot establish a reliable population effect or the value of training.

## What the successful execution establishes

The historical execution is described in [verified-gpu-20261024.md](verified-gpu-20261024.md):
review source `04ec3016c2631a2f0c08a004a2e1ecdbdb7b4fea`, actual paid source
`e31873dab5b400a1ddc236c7ac9c2440f05fdab7`, and prepared driver SHA-256
`0a10c8ba12d231dee861f61145d85a77dcac7cf1ce019276f6352cbfe817af06`.
The previously inspected `fastapi_11194` patch passed four public tests.
That task is excluded from the new pilot, together with the entire observed
FastAPI repository family and its base snapshot.

The historical prompt called R1 v2 already asks for a leading explanation, an
alternative and a discriminating check. Its result therefore does not establish
the effect of purely generic review. It remains an execution reference, and is
not silently relabeled as one of the new experimental arms.

The new lock retains all **105 source fingerprints** from the successful full
qualification, the exact container digest, the 246-wheel inventory, system and
evaluator package inventories, eight checkpoint/tokenizer/template file hashes,
and the no-LoRA R0-clean archive hash. These are checked historical identities,
not a claim that the model files were downloaded or rehashed in this preparation.
The upstream model revision beyond Kaggle asset version 2 remains unknown.
The existing operational driver, permit rules, paid branches and consumed receipts
are not modified or reactivated by this research protocol.

## Experimental arms

| Arm | Shared scaffold plus intervention |
| --- | --- |
| R0 | Exact no-LoRA R0-clean baseline, a matched five-minute budget and factual corrections to tool-contract/budget instructions. Existing starter review language remains. |
| R1 | R0 plus generic reproduction, small-change review, same-check verification, patch cleanup and a verification reserve. |
| R2 | R1 plus explicit hypotheses and forward predictions, evidence identity/dependence, belief revision, missing/interacting causes and decision value of another inspection. |

The graph tool's identifier semantics and the analyzer's read-only capabilities
are explained identically in all arms. This prevents a broken tool instruction
from becoming an accidental control condition. R1 deliberately does not add
the historical prompt's leading-hypothesis/alternative/discriminating-check text.
R2 does not add a tool, reasoning engine, adapter or budget.

The builder verifies the original six file hashes before making any change. All
arms have byte-identical `agent.yaml`, `sub_agents/code_analyzer.yaml`,
`configs/sampling.yaml` and `eval_config.yaml`. Only the two prompt files differ
between arms, and additions are nested: R0 is a prefix of R1, which is a prefix
of R2. Authored prompt files and all resulting archive members are fingerprinted.
The resulting archives must still pass the actual official compiler/schema and
original-tool checks before a future run. Assembly is not official validation.

## Common runtime and budget

| Item | Frozen value or required accounting |
| --- | --- |
| Checkpoint | `google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2`; exact eight-file hashes in the protocol; no adapter |
| Serving | A100 PCIe 80GB x1, native BF16, TP1, context 32768, custom all-reduce disabled, `gemma4` parsers |
| Runtime | Digest-pinned PyTorch 2.10.0/CUDA 12.8 image and the successful runtime inventory, including vLLM 0.19.1 and corrected FastAPI 0.136.3 |
| Sampling | Temperature 0.2, top-p 0.95, max output 16384, configured thinking budget 4096, include thoughts true; original sampling bytes unchanged |
| Agent work | 300 seconds per task, including inspections, delegated work and retries |
| Charged tools | 30 shared charged calls, using the official accounting semantics |
| Model requests | At most 50 total requests, including delegates, retries and compaction; new enforcement and coverage **NOT RUN** |
| Commands | At most 60 seconds, also bounded by remaining work time |
| Child process | 330 seconds including teardown; the final 30 seconds are not extra reasoning time |
| Context and state | Fresh task workspace, agent session and conversation for each arm; no traces, edited files or outcomes passed to another arm |

These are matched maximum allowances, not a promise of equal realized inference
work. Longer prompts consume time and tokens. There is no dummy padding to make
the prompts the same length. Record actual prompt/output/reasoning token counts,
including missing-counter status, and actual model request counts. Historical
wire receipts contain hashes and HTTP status but do not establish complete token
accounting or enforcement of every delegated/retried request. An accounting gap
must block a strict matched-inference claim. Sampling enforcement, cache policy
and seed behavior must be recorded at actual run time; reproducible ZIP bytes do
not make stochastic model output deterministic.

## Preselection without inspecting task content

**Actual v2 selection: SELECTED — six primary tasks, six reserves, three repository
clusters.** Free CPU run
[40072228708](https://github.com/hynk-studio/backtrace/actions/runs/40072228708)
produced the committed [selection receipt](research-selection-20261024.json) and
[verification receipt](research-preparation-cpu-20261024.json). It also downloaded
the exact original R0 ZIP and assembled all three candidate archives successfully.

The earlier free CPU run
[40071820909](https://github.com/hynk-studio/backtrace/actions/runs/40071820909)
acquired the original pinned JSONL and verified all 129 IDs. Its metadata showed
that excluding the 67 FastAPI tasks leaves **62 tasks across only three
repositories**: `psf/requests`, `textualize/rich` and `encode/httpx`. The original
six-repository requirement could not be satisfied. The initial receipt is retained
in [research-preparation-initial-cpu-20261024.json](research-preparation-initial-cpu-20261024.json),
and the exact v1 protocol bytes are retained in
[research-comparison-protocol-v1.json](research-comparison-protocol-v1.json).

The explicit v2 amendment uses this metadata fact before any problem content or
model outcome was inspected. It preserves the original seed, hash ranks,
exclusions, prompt bytes and all budgets. It keeps six primary tasks and six
reserves, traversing the same ranked repositories in round-robin order with a
minimum of three primary repository clusters. This changes the sampling design;
it does not retroactively convert the v1 shortfall into success. HTTPX has only
one eligible task, so a requirement of two tasks per repository would be invalid.
The v2 receipt was produced by a fresh selector execution on the same source.

| Slot | Public task ID | Repository | Arm order |
| --- | --- | --- | --- |
| 1 | `requests_7309` | `psf/requests` | R0, R1, R2 |
| 2 | `rich_3486` | `textualize/rich` | R0, R2, R1 |
| 3 | `httpx_3672` | `encode/httpx` | R1, R0, R2 |
| 4 | `requests_7315` | `psf/requests` | R1, R2, R0 |
| 5 | `rich_3067` | `textualize/rich` | R2, R0, R1 |
| 6 | `requests_7502` | `psf/requests` | R2, R1, R0 |

The six ordered reserves are `rich_3782`, `requests_7427`, `rich_3061`,
`requests_6757`, `rich_4077`, and `requests_6644`. The receipt binds each task to
its exact base commit. Eligible counts are Requests 13, Rich 48, HTTPX 1.
The resulting 18 model runs are a plan; none has executed.

The exact source identity is 1,984,455 bytes, SHA-256
`e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6`,
129 distinct public IDs. The free workflow emits only a safe metadata receipt and
deletes the raw JSONL on exit. No unseen task ID is invented, and fixture-selection
tests do not count as execution of the v2 selection.

The ready selector first checks that byte identity, then parses a conservative
schema. Duplicate IDs (including identical duplicates), ambiguous JSON keys,
unexpected fields, malformed metadata, a missing known exposed task, or a changed
repository identity fail closed. A future schema amendment must inspect only
field names/types first and must not use task difficulty or outcomes.

Only `instance_id`, `repo` and `base_commit` enter the selection projection.
Problem statements, hints, reference patches, test patches and test names are
never printed, ranked, copied into prompts or included in the selection receipt.
The JSONL is read in a preparation process, not by the agent. Reference labels
remain evaluator-only storage. The safe receipt binds the source, metadata
projection, exclusions and protocol by hash.

Selection is fixed before outcome inspection:

1. Exclude `fastapi_11194`, `fastapi/fastapi`, `tiangolo/fastapi` and the seen base
   commit `a7f2dbe976bf72703376f0cd04487bfc4a849f83`.
2. Rank repository names by SHA-256 of the committed seed and repository identity;
   rank task IDs independently within each repository. Literal identity breaks a
   hash tie. Traverse repositories in that fixed order, taking each repository's
   next ranked task per round while it has one. The first six are primary tasks;
   they must cover at least three repositories.
3. Continue the same traversal for the next six unused tasks as ordered reserves.
   A repository with only one task is exhausted after its first contribution.
4. Assign the six permutations of R0/R1/R2 to the six primary tasks. Every arm
   appears twice in each order position. Each task receives all three arms once.
5. Report `SELECTION_SHORTFALL` if there are fewer than three primary repository
   clusters, six primary tasks or six reserves. Emit eligible counts per repository
   and the actual primary cluster count. Do not silently relax exclusions or call
   a smaller pilot complete.

Reserves are not automatic replacements. Only a documented unavailable or corrupt
input discovered before any arm outcome can motivate a selection amendment.
Prefer a reserve from the same repository, preserve the original slot and failure
evidence, and freeze the amendment before a model run. Never replace a difficult
task, timeout, incorrect patch or inconvenient model result. A repository is a
conservative family proxy, not proof that tasks are semantically independent.
“Uninspected” means no recorded project inspection; public or pretraining exposure
cannot be ruled out.

## Outcomes, denominators and verification

The primary outcome is independently resolved tasks within the frozen work,
request and tool allowances. Each of the 18 assigned task/arm slots retains an
outcome: `RESOLVED`, `INCORRECT`, `TIMEOUT`, `PARTIAL_PATCH`, `NO_PATCH`,
`MODEL_ERROR`, `INFRA_FAILURE`, `INVALID_ARTIFACT` or `NOT_RUN`. Model failures,
budget exhaustion and infrastructure failures remain in the assigned denominator.
Unrun slots remain explicit; no effect estimate is produced for an incomplete
pilot. Report operational and model-failure categories separately so a source of
missing correctness evidence is visible.

Record the exact candidate/source/model/runtime identity, actual accounting,
original patch/trace/wire hashes and independent JUnit counts/hashes. The paired
table has one row per task and one outcome per arm. Report R1–R0 and R2–R0 along
with the principal incremental R2–R1 contrast. The summary produces only paired
win/loss counts and resolved-rate differences when all planned outcomes exist.
It does not fabricate a confidence interval or claim statistical significance.
The actual source supports three repository clusters. Six tasks from these three
clusters and one stochastic repetition cannot
support a confident general improvement claim; a later study needs a larger,
predeclared sample/repetition plan and uncertainty that respects repository
clustering. Do not extend or stop the study based on a favorable interim score.

The historical process flag `NO_COMMAND_AFTER_LAST_ACCEPTED_MUTATION` is retained
as a common measurement. It says no recognized command followed a recognized
`write_file`/`edit_file`; it does not establish coverage of shell mutations or all
delegated traces. Conversely, a later command or zero exit is not proof that a
relevant test ran. Store `relevant_same_check_rerun` as YES/NO/UNKNOWN, the final
mutation/check ordering and coverage status; keep independent patch correctness
separate. A trace analyzer alone cannot certify a same-check retest.

## CPU commands

Run these from the repository root. Output paths must be new; existing files and
directories are never overwritten. Candidate bytes and private task metadata
stay under ignored `.local/` paths.

```sh
python3 -m tools.research_comparison validate
python3 -m tools.research_comparison build .local/research-inputs/r0-clean.zip .local/research-candidates-v2
python3 -m tools.research_comparison select .local/research-inputs/tasks.jsonl .local/research-selection-v2.json
python3 -m tools.research_comparison summarize docs/research-selection-20261024.json .local/outcomes-v2.json .local/summary-v2.json
python3 -m unittest discover -s tests -p test_research_comparison.py -v
```

The summarize input is a JSON array of outcome records. Each identifies
`instance_id`, `arm` and `outcome`; `RESOLVED` additionally requires explicit
`independent_evaluator_resolved: true` and `within_matched_budget: true`.
Those fields must be backed by the artifact/accounting evidence described above.
The summarizer is bookkeeping, not a substitute for a verifier or runtime guard.

The selected IDs and base commits are now fixed. Before any GPU run, acquire and
freeze their task asset hashes, validate the three real candidate archives with the
official tools, implement and qualify the new task-parameterized runner and full
request accounting, and obtain a concrete capped compute authorization. R3's
training/save/reload/attachment feasibility work is a separate subsequent step.
