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

No model stream, launch permit, GPU initialization, model server or actual
model/agent task is entered. Paid hardware checks retain their defaults and
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

Actual results pending. The projected complete report and owner-encrypted
private logs will be retained, with exact source/run/file hashes. New reference
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
qualification is still pending.

All work here is free CPU/read-only source acquisition. No further GPU create,
paid job rerun, top-up, automation activation, merge or submission is authorized
by this preparation. Any remaining actual CUDA, model loading and inference
observations must be distinguished from these CPU results.

Meta-assessment: the new check directly exercises the previously omitted
installation boundary with real inputs and the same production orchestrator.
Lifetime inspection can identify stale/short-lived sources before a later paid
proposal; it cannot establish a retrospective cause for older failures.
