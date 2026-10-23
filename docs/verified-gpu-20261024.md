# One conditional R1 v2 GPU diagnostic

Related: Issue #1, Draft PR #19. Owner instruction: **그래픽 자원 있으면 시도하자**.
This authorizes one bounded attempt after full free qualification of the new
operational identity. Base: `8b7b1416eec1d714dfbb581e4aa06a06793f2c27`.

Use `owner-verified-gpu-20261024` and the separate review/start/watch branches
in `verified-gpu-authorization-20261024.json`. Historical paid heads, claims,
receipts and all 237 baseline state blobs remain immutable.

At 2026-10-24 07:29:04 KST read-only run39822924063 attempt12/job120688469944
found zero Pods/current spend, auto-pay false, USD5.7669749701 balance, and
CA-MTL-3 A100 PCIe80GB stock. Hourly compute+100GB temporary disk was USD1.804;
the 7200-second worst-case cost USD3.608 fits the USD8 cumulative stop at
USD7.8410250299. This observation does not reserve stock. Recheck at creation.
Original artifact12536396252 ZIP SHA256:
`c37bfe3305db16302a44a33c07c9c5eb356b45ecac61407d6244163dccb98d20`.

The candidate remains protocol `R1-budget5m-verification-guidance-v2/A10080-TP1`,
prepared driver SHA256 `0a10c8ba12d231dee861f61145d85a77dcac7cf1ce019276f6352cbfe817af06`,
with 300 seconds, 30 charged tools, 50 LLM calls, 60-second commands and a
330-second child deadline. It uses generic budget reservation and same-check
verification guidance. Official tools, model/task bytes and sampling are unchanged.

Full CPU qualification tests actual transport/setup/HTTP/tool/recovery and
cleanup failure controls. It cannot prove Gemma follows the guidance or solves
the task. Actual execution must independently establish model behavior, patch
correctness on the original public tests and successful server teardown. The
previously inspected public task remains diagnostic, not a held-out score.

Launch gates: all current source bindings and full free stages pass; original
private receipts independently verify; active schema-1 receipt matches; final
source Linux and free owner preparation pass; fresh same-source watcher exists;
current hardware/stock/account/cumulative budget qualify. No paid launch has
yet occurred at this checkpoint. No automatic second allocation.

A pre-launch integration review found that the controller still labelled new
claims with the preceding R1 v1 protocol although the prepared task was R1 v2.
The controller label now matches the prepared candidate. A regression compares
an actual projected claim against `cloud_task.RUN_NAME`; without this correction
the post-deletion verifier would reject the mismatched experiment identity.
The first new-source free run40034617157 is superseded before any paid launch;
its passed Linux run40034617261 (365 tests) is retained as intermediate evidence.
A fresh full free run and Linux suite must qualify the corrected source.

The deeper production permit boundary also rejected the current R1 v2 name
with `unknown calibrated permit run`, before model start. The original full
free setup intentionally exercised CPU prerequisites without a launch permit,
so that boundary was missing from coverage. A root-owned temporary fixture now
passes a real projected controller claim into the actual task permit consumer:
the current protocol passes once, replay fails, and the previous protocol
cannot enter the current task. The test failed before the permit allowlist fix.
The permit consumer now explicitly accepts both known R1 protocol versions
while retaining exact permit-to-task matching, expiry and single-use checks.
The prepared driver and candidate prompt bytes remain unchanged; its deployed
`a100_task.py` helper is intentionally updated and must be fully requalified.
Run40035020575 is also superseded; its Linux366-test pass alone missed the
consumer boundary. Preserve that intermediate evidence rather than treating it
as final launch qualification.

## Full qualification checkpoint

Final full free run **40035577327** at
`6b6929c1a6ca91f5a69778c6dc80dd282eeb07a2` passed all **24 stages**.
Linux **40035577321** passed **366 tests** and the real HTTP regression.
Independent inspection verified all105 source hashes, all152 owner-private
records, seven original-tool cases on host and exact offline image, four
JUnit hashes/counts and the retained SSH CPU log hash. Actual setup took
290.638 seconds. Real lost/false acknowledgement cleanup controls passed;
all disposable containers had two successful absence reads.

See `verified-gpu-free-result-20261024.json`,
`verified-gpu-free-execution-20261024.json` and
`verified-gpu-actions-qualification-20261024.json`. The two intermediate free
runs were deliberately superseded before completion and are not qualification.
Their original logs and Linux artifacts are retained. This final proof still
does not establish model behavior, correctness or actual GPU teardown.

The schema-1 receipt now binds the corrected source. At this checkpoint the
new claim remains unused; receipt-source Linux and free owner preparation, a
fresh matching watcher and current offer must still pass before allocation.

## Actual one-attempt outcome

The scope is now **CONSUMED**. Owner [40039468878](https://github.com/hynk-studio/backtrace/actions/runs/40039468878)
and independent watcher [40039393307](https://github.com/hynk-studio/backtrace/actions/runs/40039393307)
completed successfully from immutable source
`e31873dab5b400a1ddc236c7ac9c2440f05fdab7`. One EU-RO-1 A100 PCIe80GB Pod
`gvms91slerswyj` was allocated at **2026-10-24 08:25:26 KST**. The final fresh
offer qualified EU rather than the earlier CA observation. All historical
paid/watch heads, claims and receipts remain immutable.

| Outcome | Observed result |
| --- | --- |
| Model/runtime | Native SM80/BF16, TP1; HTTP ready after 159.347s |
| Agent task | Submitted in 196.630s, 27 charged tools, 29 LLM calls; strict v2 completion PASS |
| Patch | 7,745 bytes, SHA256 `0e2e0d87cb71173732ca2e458373ad52f5d4d489e18a0131dff0cc2476dc3ab1` |
| Public correctness | Exact recovered patch: **4 passed, 0 failed, 0 errors/skips; resolved** |
| Server/process cleanup | `server_stop_returned`, worker exit0, no UID survivors, scratch removed |
| Provider cleanup | Owner and watcher each confirmed two absence reads; owner status COMPLETE |

The original public/private artifact ZIPs were retained and their digests
verified. All17 private owner records, the eight-file delivery manifest,
patch/task/wire/ATIF bindings and cleanup events were independently checked.
Free evaluator [40041608780](https://github.com/hynk-studio/backtrace/actions/runs/40041608780)
at `bf50a54525b8d78ebe7bb021ea517219c45d70d3` received four byte-identical
original receipts through a fresh encrypted receiver. It required completed
original owner plus two deletion absence reads before running the public tests.
All12 evaluator-private records and the actual four-test JUnit hash/counts were
checked. No model/agent rerun, provider mutation or reference control occurred.
Its Linux suite passed366 tests in29.712s. See the paid and public-evaluation
result/execution JSON files next to this report.

## Did the preparation prevent real failures?

The two paid-entry defects had deterministic failing regressions before their
fixes, and the corrected v2 claim/permit path now reached actual model execution.
The previous server ownership fix also completed actual GPU teardown here,
including an empty outer cleanup and independent provider deletion. Those are
direct execution observations beyond the earlier scripted CPU coverage.

The verification prompt remains incomplete as a behavioral safeguard. There
were no rejected edits or charged-tool exhaustion, and five reproduction
scripts used explicit nonzero failure exits. However, after the one production
edit the model submitted without rerunning a check, with three tools and about
103 seconds still available. A sixth reproduction script caught and printed
failures, but its observed execution stopped earlier on a missing pytest
import; two further inline commands had syntax errors. The process diagnostic
therefore correctly retains `NO_COMMAND_AFTER_LAST_ACCEPTED_MUTATION` despite
the independently correct patch. Do not turn the public-test pass into a claim
that same-check verification was followed or enforced.

The submitted patch also contains six exploratory reproduction scripts. Public
task correctness is established for this one recovered patch, not production
patch cleanliness or general model competence. The task was previously inspected
and repeated; this is not held-out performance or a matched causal comparison
against R0/R1. A useful next free design question is a generic final-edit
verification condition compatible with the pinned official tool contract.
Do not add task-specific evaluator answers or silently change the experiment.

At **2026-10-24 08:55:03 KST**, independent read-only account run39822924063
attempt14/job120715833063 found **zero Pods, zero current spend/hour, auto-pay
false**. Balance USD4.9937691886; observed decrease USD0.7732057815 from the
pre-run wallet, cumulative observed spend USD5.0062308114. This is an observed
wallet debit, not a final invoice; settlement may lag. No additional funding,
settings change, second allocation, paid rerun, merge or competition submission.
