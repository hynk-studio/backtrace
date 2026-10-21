# Connected-path recovery audit (free work only)

The owner asked to track down the structural preparation failures, correct
overlooked faults, and repeatedly assess whether the checks prevent actual paid
failures. This follow-up is stacked on PR #8 at
`d604960a2bd3bb0efc7e428f08d4f14c80eabf58`. All prior paid claims remain consumed.
There is no new paid authorization, start/watch branch, or provider create here.

## Findings and corrections under qualification

| Failure mechanism | Correction | Evidence required before calling it qualified |
| --- | --- | --- |
| Real HTTP probe omitted mandatory driver requests | Production and CPU use one metadata exchange; a narrow middleware reads the initialized engine's actual model/dtype/parallel config, followed by native model listing | Missing middleware fails the entire driver; absent state returns 503 and wrong dtype is rejected |
| CPU task construction stopped before runner entry | Run the whole prepared `server_phase` and its actual task subprocess with scripted content only at the model boundary | Real HTTP schemas, LiteLLM/ADK, official runner, actual selected snapshot and sandbox, real shell/submission tools, trace and patch |
| Official runner can return an error without nonzero process exit | Validate the emitted task result and actual model request/response receipts inside the task | Error response produces nonzero actual task/driver exit |
| Worker treated process exit zero as completion | Revalidate actual transferred patch, counts, wire and ATIF trace before reporting finished | Missing, changed or incomplete artifacts rejected after real byte transfer |
| Recovery could be skipped near deadline or mask a prior failure | Require recovery for success and retain the first workload exception if recovery also fails | Expired recovery and workload-plus-recovery-failure controls |
| Scientific correctness was conflated with plumbing | Report task completion separately from patch evaluation | No authored response can establish model quality or a resolved task |
| A first free probe failure concealed unrelated later checks | Collect independent post-prerequisite probe failures, on host and pinned image | Later checks execute after an earlier failure; overall status remains FAIL |
| Actual graph loader calls `endswith` on directories, but the driver passed `Path` | Convert the same pinned graph/embedding paths to strings at the official context boundary | Execute search, neighbors and subgraph tools in the actual task |
| Isolated evaluator UID could not traverse the source checkout | Copy the qualified verifier worker into its private UID-owned staging directory | Actual public-test negative and positive controls under UID 65533 |
| Missing pytest exits 1, which could be mistaken for an unresolved model patch | Install hash-pinned evaluator-only dependencies and require actual JUnit tests with a consistent outcome | Missing receipt, collection errors, skipped-only runs and contradictory counts are rejected |

## What this check can and cannot prevent

The deterministic CPU content asks the real `run_command` tool to append a
neutral transport marker to README, submits that diff, and returns a final
message. No solution or reference patch is used. The CPU check is a deliberate
transport/tool exercise on the real public-task snapshot, not an attempted
solution and not a model result. The existing model, prompts, candidate,
sampling, task input hashes and inference limits remain pinned.

GPU identity/start and the chat generation handler with scripted content are substituted. Actual
vLLM route handlers, middleware and request/response schema validation execute;
Gemma token generation and its tool/reasoning parser do not. Both the Actions
host and pinned deployment image must pass. The image has no external network.
The full driver setup and controller/transport lifecycle checks remain separate
requirements, and must not be renamed complete GPU qualification.

The model-facing driver does **not** mount the evaluator-only record. A separate
free CPU verifier is being qualified with a different UID: the neutral README
transport patch must fail the actual public tests, and the original public
reference patch must pass. The latter is only an evaluator positive control;
it never enters agent inputs or scripted model responses. Neither control is
a model score, competition acceptance, or hosted scoring.

## Status

Pinned five-wheel private source acquisition: PASS in free Actions run
39676417093; original wheel hashes verified before inspection. A preceding YAML
syntax error in the newly added acquisition workflow was corrected before the
job ran. No acquired third-party bytes enter the public branch.

Local artifact/recovery negative tests and local-tooling preflight: PASS.
Actual full-runtime connected-path checks: **PARTIAL PASSES; OVERALL FAIL**.
No corrected complete pinned-image pass exists yet. The old launch receipt is stale and cannot
qualify the changed operational files. Do not infer paid readiness from unit
test count or this implementation plan.

The pinned upstream API supports custom middleware through `args.middleware`.
The new hook reads only `app.state.vllm_config`, which upstream `init_app_state`
sets from the engine client. It performs no environment collection or inference.
Production stays loopback-only with vLLM development mode disabled. The ordinary
vLLM health and models handlers remain actual installed handlers. A free child
also exercises the real startup shim and wrapper environment to import the
middleware from the hash-qualified, read-only workload code tree.

Exploratory full run 39677844088 at
`46377688c2c789319469c5d9d3c0070849ca7859` passed offline runtime installation
but failed on the newly exercised `/server_info` HTTP request with 500. The CPU
probe originally retained only the client exception, omitting its captured ASGI
traceback; that evidence-capture defect is corrected. The incomplete CPU engine
state fixture is being corrected without changing the real route or serializer.
This failed run is not qualification. Its exact-source Linux run 39677843869
passed 289 tests and the minimal HTTP controls; those passes did not override it.

Run 39679368908 at `8fb8c5ce539f7fb1ac2e9b3cf84ff2d877131aaf`
retained the original cause: the broad upstream system-environment collection in
`/server_info` exceeded the 30-second client timeout. Its incomplete CPU config
fixture also emitted serialization warnings. Enabling that developer endpoint
was reconsidered: it is no longer a mandatory production request. The narrow
engine-state middleware replaces this avoidable dependency. This run did not
qualify the connected task or image. Linux run 39679368961 passed separately.

Consolidated run 39681137641 at
`48effc94d10bb6685a861c29d5fc52a1e84d018d` passed actual installed-vLLM HTTP
controls, original inputs, actual UID/sandbox prerequisites and all five
concurrent owner/watcher cases. Connected task and pinned-image checks failed.
The final unprivileged evidence collector then hit PermissionError while
traversing root-owned private outputs; original task-error logs were not
exported. The public stage observations survive, but the underlying task/image
causes remain unaudited for this run. It is not qualification.

The replacement collector reads private logs as root and exports only encrypted
bytes to the ordinary controller. It preserves the complete stage report if
export fails and can export an early encrypted host checkpoint before waiting
for image/controller checks. An actual different-UID ciphertext/plaintext access
test is required before installing the large runtime. The local managed executor
cannot map UID 65533 (chown returns EINVAL), so that check requires free Linux CI.

Run 39684433596 at `a2223134329a581e5cd3601f9e2c0c87cddfa2fb`
passed the real different-UID evidence-export precheck and actual vLLM HTTP
controls. Its complete driver/basic shell/patch/ATIF/recovery scenario passed
with three real chat HTTP requests. Missing metadata produced driver exit 1
before a model call, and actual model HTTP 400 produced a nonzero task/driver
exit. The full-tool and separate evaluation stages failed, so the run cannot
qualify the changed path. Exact-source Linux run 39684433451 passed 292 tests.

The early encrypted diagnostic was successfully read as root and exported as
ciphertext (SHA-256
`265fde680158003e36ea6ffd3fdb9d56b3277176609900ee7aa4e24d866d33d5`).
Unlike the prior lost-log run, it retained the original causes: actual
`search_similar_code` returned `SimilaritySearchError` because its directory
was a PosixPath instead of a string; the evaluator UID could not open the
verifier in the private source checkout. The exact acquired embedding utility
also reproduces Path failure/string success locally. The production derivative
now converts only those two context arguments, preserving paths and scientific
constants. The evaluator stages only its qualified worker under UID 65533,
without exposing the source checkout or reference record to the agent.

The scripted scenario exercises all declared workspace/graph tools and the
unchanged code-analyzer AgentTool within the same 10-tool/50-turn budget. It
uses public graph identifiers and neutral file edits, not reference answers.
An assertion failure at that scripted content boundary now yields a terminal
400 instead of a synthetic 500 retry ladder, and actual receipts are retained
even when a case fails. These corrections still require a fresh full run.

Meta-assessment: this expanded check found a real production graph-API mismatch
after the narrower shell/submit check passed. That is useful evidence of
failure prevention. It is not evidence of Gemma generation/parser compatibility,
a correct solution, or permission to repeat a paid allocation.

The final encrypted export for 39684433596 succeeded (36 private files;
ciphertext SHA-256
`68a8fbc3148cca31c965739cb042cc71e3b1544f8bfb11fbc598003edbb746cd`).
All five independent concurrent controller cases passed. The image's connected
test used the bootstrap system Python instead of its installed runtime, so its
children could not import uvicorn/adk_submission. This is a qualification-runner
defect, not observed failure of the production runtime; image runtime and actual
UID prerequisites passed separately. The image now enters the whole connected
test through `/opt/backtrace-runtime/venv/bin/python`, as the host does. This
additional correction also needs a fresh complete qualification.

Run 39687329560 at `c29dd27a474cd860510c0e9eda721e759f0fb9e2`
passed every host connected-driver case, including all declared workspace/graph
tools and code-analyzer delegation (13 actual chat HTTP requests). Actual basic
task/recovery and both missing-route/model-error controls passed as well. The
evaluator worker now ran under its separate UID, but both controls exited 1
because pytest was absent. The positive control correctly prevented this from
being reported as successful evaluation; overall qualification remains FAIL.

The new evaluator-only closure pins pytest 8.3.5, iniconfig 2.1.0 and pluggy 1.5.0
to wheel hashes and sizes observed from official PyPI release metadata on
2026-10-21. Its private wheels and site-packages never enter the model/agent
runtime or task manifest. Verification also observes the real JUnit file before
official sandbox teardown: missing/errored/skipped-only tests cannot become an
unresolved model score, even when the process exits 1. Both public control
results still come from the unchanged official verifier and actual test patch.
The exact three wheels were acquired locally with manifest/hash verification;
an offline target installation ran real pytest 8.3.5 and produced valid JUnit
for one deliberate assertion failure and one passing selection. This is a
dependency/receipt smoke, not yet the selected public-task control result.

The latest local discovery additionally observed a TLS rejection arriving as a
TCP reset rather than an SSLError. The negative control now accepts that exact
rejection form while still requiring that no executable was written and the
authenticated owner can subsequently complete delivery. The known local procfs
limitations remain; this is not a complete local pass.
