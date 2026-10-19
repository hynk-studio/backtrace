# Actions controller migration

The owner accepted the cloud-browser/Actions/RunPod proposal at 20:31:26 KST
on 2026-10-19. The new policy is `a100-cloud-policy.json`: setup up to 90 minutes,
allocation through confirmed deletion up to two hours, one further allocation,
server start and public task at most, within the existing USD 10 wallet and
USD 8 cumulative stop. The prior CA-MTL-3 attempt remains consumed and deleted.

## Observed execution

- The public Draft PR remains #7 on `bt-001-a100-cpu-qualification`; main is untouched.
- First Actions run: https://github.com/hynk-studio/backtrace/actions/runs/39246227301
- Source: `65a6a4f539929fcaaee23be98ef55bd54a9c8606`.
- Ubuntu 24.04, qualified Python 3.12.14, actual root Linux PID namespace check.
- **169/169 existing tests passed in 25.247 seconds**, preflight READY.
- Secret-free CPU log artifact retained for seven days; no private inputs uploaded.
- New component tests: 25/25 passed locally. These use synthetic HTTP/provider
  fixtures; they do not establish live storage throughput or paid cancellation.
- No new allocation, key creation, secret transfer, inference or task execution.

## Implemented components

`direct_delivery.py` downloads exact files directly on the receiving host using
short-lived HTTPS storage URLs. A separate owner-side resolver must obtain those
URLs. The downloader sends no account authorization header, refuses redirects and
unreviewed hosts, validates strict Range responses after an interrupted body, has
bounded retries and a shared deadline, and verifies every original size/hash.
Single-member ZIP transport is decoded only to the expected file. Wrong bytes,
extra files, bad paths and expired deadlines never activate the input directory.

`cloud_state.py` writes only allowlisted metadata to the dedicated
`bt-001-a100-state` branch. Its fixed authorization claim is create-only, read
back before a provider POST can be attempted, and never reset on a timeout,
restart or empty provider list. Local bootstrap keys, signed URLs and payloads
are excluded from this public record. Prior wallet consumption is included in
the two-hour quote. Ordinary workflow reruns cannot claim another allocation.

`cloud_watch.py` runs in a separate Actions workflow. It observes the exact
controller run and its heartbeat, finds a lost create response by the immutable
random Pod name, and only stops/deletes that owned Pod. Two exact-ID/list absence
reads establish deletion. No resource observed after an uncertain create is
reported separately from confirmed deletion. GitHub write failure cannot suppress
provider cleanup after the claim has been read. The watcher contains no create
operation and does not start the workload.

The cleanup workflow is scoped to the exact
`bt-001-a100-watch-20261019` branch; it is not triggered by routine PR pushes.
Its independent concurrency group never cancels a running watcher. The
`claim_before_create` integration seam also checks that this separate workflow
is currently running at the same source SHA before allowing a claim. These
branches have not been activated. No paid-start workflow is published yet.

## Remaining launch prerequisites

1. Sign in to GitHub in the cloud browser to configure the controller's RunPod
   and Kaggle credentials through repository secrets, without values in chat.
   The connector can edit source and read runs but does not expose secrets APIs.
2. Resolve the already authorized private input assets at their pinned versions;
   preserve prepared private driver and transport binaries outside public Git.
   Validate actual download URLs, wire encodings, sizes and access before spending.
3. Bind the new timing policy into the retained private driver, permit, activation
   and owner-worker lifecycle. Preserve the scientific AST and inference budget;
   qualify that exact resulting driver hash on CPU. The old paid entry remains
   disabled and its original timing policy is deliberately unchanged.
4. Connect periodic durable heartbeat and private result retention, then qualify
   the complete start/worker/watch flow. Raw task output must not become a public
   Actions artifact. Verify the fresh account quote and existing wallet balance.
5. Start the independent watcher first, observe readiness, then one controller
   run. Preserve cleanup evidence and confirm actual billing after completion.

Until those prerequisites pass, the new code is migration preparation and
**not authorization to invoke an unqualified paid entry**. An Actions/GitHub or
provider outage can still delay cleanup; no provider hard timer is claimed.

References #1. No merge, Issue #1 closure, training or submission.
