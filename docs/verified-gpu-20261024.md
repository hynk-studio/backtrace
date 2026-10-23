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
