# Connected-path recovery audit (free work only)

The owner asked to track down the structural preparation failures, correct
overlooked faults, and repeatedly assess whether the checks prevent actual paid
failures. This follow-up is stacked on PR #8 at
`d604960a2bd3bb0efc7e428f08d4f14c80eabf58`. All prior paid claims remain consumed.
There is no new paid authorization, start/watch branch, or provider create here.

## Findings and corrections under qualification

| Failure mechanism | Correction | Evidence required before calling it qualified |
| --- | --- | --- |
| Real HTTP probe omitted mandatory driver requests | Production and CPU probe call the same metadata exchange; enable vLLM developer metadata on the existing loopback-only server | Actual installed vLLM `/server_info` and models response; development-disabled negative control fails the actual driver |
| CPU task construction stopped before runner entry | Run the whole prepared `server_phase` and its actual task subprocess with scripted content only at the model boundary | Real HTTP schemas, LiteLLM/ADK, official runner, actual selected snapshot and sandbox, real shell/submission tools, trace and patch |
| Official runner can return an error without nonzero process exit | Validate the emitted task result and actual model request/response receipts inside the task | Error response produces nonzero actual task/driver exit |
| Worker treated process exit zero as completion | Revalidate actual transferred patch, counts, wire and ATIF trace before reporting finished | Missing, changed or incomplete artifacts rejected after real byte transfer |
| Recovery could be skipped near deadline or mask a prior failure | Require recovery for success and retain the first workload exception if recovery also fails | Expired recovery and workload-plus-recovery-failure controls |
| Scientific correctness was conflated with plumbing | Report task completion separately from patch evaluation | No authored response can establish model quality or a resolved task |

## What this check can and cannot prevent

The deterministic CPU content asks the real `run_command` tool to append a
neutral transport marker to README, submits that diff, and returns a final
message. No solution or reference patch is used. The CPU check is a deliberate
transport/tool exercise on the real public-task snapshot, not an attempted
solution and not a model result. The existing model, prompts, candidate,
sampling, task input hashes and inference limits remain pinned.

Only GPU identity/start and model-generated content are substituted. Actual
vLLM route handlers, middleware and request/response schema validation execute;
Gemma token generation and its tool/reasoning parser do not. Both the Actions
host and pinned deployment image must pass. The image has no external network.
The full driver setup and controller/transport lifecycle checks remain separate
requirements, and must not be renamed complete GPU qualification.

The current private driver explicitly does **not** mount the evaluator-only
record or run patch evaluation. Even a completed agent task cannot establish a
resolved public task. That limitation remains a blocker for any claim of full
evaluation readiness; no competition acceptance/scoring is implied.

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
