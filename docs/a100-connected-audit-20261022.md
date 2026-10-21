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
Actual full-runtime connected-path and pinned-image checks: **NOT YET RUN** at
this implementation checkpoint. The old launch receipt is stale and cannot
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

An additional scripted scenario exercises all declared workspace/graph tools
and the unchanged code-analyzer AgentTool, within the same 10-tool/50-turn
budget. It uses public graph identifiers and neutral file edits, not reference
answers. That extended scenario is still awaiting execution at this checkpoint.
