# Complete free setup and source-lifetime checks

The owner requested all available checks before another retry. This scope
continues the two recommended free checks: actual frozen inputs through the
entire SSH runtime installation and retained CPU driver preparation; and
read-only source lifetime/header checks. Base: Draft PR #13,
`aa391853494f1b6c67bcdcc10ceb09fdf3e72b4a`. References #1.

## Execution design

The existing complete free qualification now includes a real deployment-image
container with the fixed TLS/pinned SSH transport, the exact manifested driver,
and all actual frozen wheel/task streams. It calls production
`cloud_worker.setup_remote` unchanged through runtime_installation. At the
runtime_hardware boundary the CPU test stops explicitly, runs the existing
`runtime(require_gpu=False)` check, activates only the verified task directory
using existing verification/permission functions, and invokes the retained
driver's `--cpu-prerequisites` entry over the same SSH connection.

No model-weight stream, launch permit, GPU initialization or actual Gemma
server/task is entered. Paid hardware checks retain their defaults and
are not weakened. The child has no account credentials; scoped URLs arrive
only through a private file and authenticated stdin. Only source counts,
hashes, known stage results and declared lifetime aggregates may be public.

The complete free qualification also reruns the existing host/pinned offline
image driver, HTTP, connected scripted-model/tool/retrieval/evaluator controls,
and concurrent owner/watcher scenarios. Scripted model content is plumbing
evidence and is never counted as actual Gemma output or a model score.

## Source lifetime

Before installation the owner records aggregate declared expirations for the
already resolved frozen sources. It interprets GCS V4 as X-Goog-Date plus
X-Goog-Expires and legacy V2 as the Unix Expires timestamp. Unknown signatures
stay UNVERIFIABLE; public package hosts without a query are distinguished from
an unknown private lifetime. These observations do not cryptographically verify
a signature or promise future availability.

Immediately after the actual SSH installation, all original model URLs are
opened in streaming mode for response metadata and closed without reading a
model body. Status, final host, Content-Length and encoding must still match
the originally resolved descriptors. This is a point-in-time access check,
separate from declared validity across the maximum 5400-second setup window.

Primary definitions checked 2026-10-22:
- https://docs.cloud.google.com/storage/docs/access-control/signed-urls
- https://docs.cloud.google.com/storage/docs/access-control/signed-urls-v2

## Evidence and limits

The corrected complete free qualification passed run **39784201691** at
`ae38cf6a831e277ed91e97daff2c6867eb14f5b8`. The projected complete report and
owner-encrypted logs were retained and recovered, with exact source/run/file
hashes. New reference
transfer files use the existing unique free-run namespace; no historical paid
claim, Pod record, start/watch head or old qualification receipt is reset.

### First free execution and corrections

Run 39782490197 at `dd257ba2eaf951e1fecf94163162eb70eaca076d` failed.
The new SSH child returned KeyError before starting a container; its clean
parent environment supplied GITHUB_RUN_ID but sudo did not explicitly preserve
it. This is corrected with `--preserve-env=GITHUB_RUN_ID`. The corrected child
also retains its traceback in the owner-encrypted private process log, so a
later failure does not lose its location. This does not establish a cause for
any earlier paid failure.

Independently, the existing host system-package download stopped with
RemoteDisconnected. Idempotent package reads now retry transient connections,
429/selected 5xx and short bodies at most three times within the original
shared deadline. Redirects, permanent HTTP errors and changed hashes remain
fatal; incomplete/unverified bytes never become package files. Four regression
tests cover transient recovery, persistent-failure bounds, permanent identity
failures and deadline exhaustion. These tests do not simulate successful GPU
execution.

The original public result is `full-setup-initial-result-20261022.json`;
encrypted artifact 12427836474 was recovered and verified. Linux run
39782490098 passed all 327 tests plus actual minimal HTTP. The first attempt's
model-header check passed but ran after a failed setup; it is not post-install
evidence. The eight model sources declared about 72 hours remaining; all eight
task URLs had an opaque/unverifiable lifetime. The corrected complete free
qualification is recorded below.

All work here is free CPU/read-only source acquisition. No further GPU create,
paid job rerun, top-up, automation activation, merge or submission is authorized
by this preparation. Any remaining actual CUDA, model loading and inference
observations must be distinguished from these CPU results.

Meta-assessment: the new check directly exercises the previously omitted
installation boundary with real inputs and the same production orchestrator.
Lifetime inspection can identify stale/short-lived sources before a later paid
proposal; it cannot establish a retrospective cause for older failures.

## Corrected observed results

The first-attempt corrected workflow completed successfully in about 29 minutes.
Exact-source Linux **39784201752** passed **331 tests** and actual minimal HTTP.
The full public report contains 24 stage entries, zero failed stages and all
84 current operational/test hashes. The new schema-2 receipt is human evidence;
it is not accepted by, or a replacement for, the historical paid launch gate.

| Boundary | Observed result |
| --- | --- |
| Exact-image mutual TLS and pinned SSH | PASS; same fixed transport |
| Frozen driver transfer | PASS; 21 files, driver SHA 174bd635… |
| Frozen runtime/task HTTPS transfer through SSH | PASS; 246 wheels / 5,373,545,117 bytes and 8 task files / 222,386,501 bytes; all manifest hashes verified |
| Production setup through runtime_installation | PASS; stopped before GPU check |
| Installed runtime and retained CPU prerequisites over SSH | PASS; 246 distributions, libcudart 12.8.90, actual UID 65534/dependency boundary and worker cleanup |
| SSH installation and CPU preparation duration | 354.482 seconds; container removed |
| Original model URLs after actual setup | All 8 metadata reads PASS; no model body read; minimum declared remaining lifetime 258,752 seconds |
| Task URL lifetime | 8 UNVERIFIABLE declarations; actual frozen task downloads PASS |
| Host plus exact offline image HTTP/connected path | PASS; actual installed vLLM routes, agent/tools/patch/retrieval/evaluator plumbing with scripted CPU model content |
| Evaluator controls in both environments | Recovered scripted patch unresolved (2/4 tests pass); evaluator-only public reference resolved (4/4); agent access denied |
| Concurrent control cases | All 5 PASS; real owner/watcher loops and CPU children with simulated provider, including stale heartbeat views, failure, cancellation and recreate rejection |
| Private evidence recovery | PASS; 92 files decrypted; SSH result matches encrypted record and CPU log hash matches |

Public result: `full-setup-result-20261022.json`, **49,920 bytes**, SHA-256
`6bf9c115323f90ffd5bf11c9539e9f92f3113d85a2fc2774fedecf53737dc4c9`.
See `full-setup-receipt-20261022.json` and
`full-setup-execution-20261022.json` for exact run/artifact/transport identities.
Owner ciphertext is **1,874,607 bytes**, SHA-256
`f02fe09242875a18e8e3381b40bc5eea99ec8e1c82345b106861f5be8a356452`;
private artifact ZIP 12431305084 has SHA-256
`2d8b38f94e7690f69481a82160586e1a9151e2b92458040e06f70ff6da9b392d`.
Keys, URL/source maps and image environment files were not exported.

All 18 consumed paid/start/watch heads and all 198 original state blobs are
unchanged. State head advanced only to add four uniquely named public-receiver/
encrypted-reference files for the two free runs. Main and old receipts are
unchanged; PR #14 remains draft.

Final assessment: the previously omitted actual-input SSH installation boundary
is now observed to pass, and the first free run exposed a child identity handoff
error plus a transient package-read failure that were corrected. This reduces
specific preparation risks and improves diagnosability. GPU memory, CUDA
execution, model loading/parser behavior and actual Gemma inference remain
NOT RUN on this source. The CPU controls do not predict a model score or
guarantee a later paid execution; no further paid allocation is authorized here.
