# Bootstrap readiness correction after the consumed GPU attempt

The 2026-10-22 instruction to inspect and improve the failure authorizes this
free correction. Review branch: `bt-001-bootstrap-diagnostics`, based on Draft
PR #10 at `bf3a650bb5b82d981e5666ac4747ff997d26d405`. References #1.

## What is established

Attempt `1af3976193e9411f8a85959dd186ed96` timed out before worker entry.
Its original diagnostic identifies the 1200-second readiness deadline, but it
does not retain the last provider state or endpoint presence. Neither a slow
image pull nor a missing TCP mapping can be established retrospectively. The
original execution record and ciphertext remain unchanged.

The acquired [official v2 schema](https://api.runpod.io/v2/openapi.json) is
274,963 bytes, SHA-256
`fe8a74b177282ec89a9ba1c75d3ce1d4bd1a2a9b9609fbdb4bd131d5b4a24506`,
identical to the previously acquired specification. The current
[Pod read contract](https://docs.runpod.io/api-reference-v2/pods/get-a-pod)
describes `status`, `ssh.direct`, and separate provisioning, starting, running
and terminal states. The readiness field names are consistent with this
contract; no API-schema change was demonstrated as the cause.

Three defects in our control path are directly visible in the paid source:

1. Readiness polling discarded each provider observation. A timeout inherited
   the last `bootstrap_heartbeat` stage, making the timeout appear related to
   heartbeat publication.
2. Owner/watcher run liveness was checked only after worker startup, leaving
   the potentially twenty-minute readiness wait outside that check.
3. Owner fixtures immediately returned a running Pod with a direct endpoint;
   the concurrent lifecycle controls never exercised a pending provider.

The old code also checked its deadline before network calls only. A slow
successful read or heartbeat acknowledgement could start a worker after that
deadline. Endpoint host/port validation was deferred to the child.

## Changed behavior

| Observation | Action |
| --- | --- |
| PROVISIONING or STARTING | Report `WAIT_PROVIDER_RUNNING`; continue within the existing limit |
| RUNNING without direct endpoint | Report `WAIT_DIRECT_ENDPOINT`; continue within the existing limit |
| RUNNING with valid root host/port | Start one worker after a fresh deadline check |
| Terminal/unknown state, absent Pod, invalid endpoint | Preserve the specific observation and clean up immediately |
| Owner or watcher finished, changed source/branch or rerun | Stop during bootstrap and clean up |
| Readiness deadline reached | Report `bootstrap_deadline`, retaining the last observation |

Every poll emits an allowlisted observation and atomically retains a bounded
history in `bootstrap-readiness.json`. This file also enters the existing
encrypted result export. Observations contain state and presence/validity flags,
not addresses, environment values, commands, keys or signed URLs.

On bootstrap failure, one read-only request to the documented
[Pod log stream](https://docs.runpod.io/api-reference-v2/pods/stream-pod-logs)
requests 50 historical lines from both sources. Sampling is limited to 32 KiB,
eight reads and a two-second socket timeout. A separate four-second caller
limit releases cleanup even if the diagnostic request stalls. The diagnostic
thread has no mutation capability and does not hold process shutdown open.
Only fixed text-signature counts, source counts and a digest are retained;
raw log text is never stored or exported. These signatures are diagnostic hints,
not causal proof. Permission, transport, empty-stream or parsing failures leave
the primary failure and exact-ID deletion intact.

## Validation and remaining limits

Focused tests exercise the actual owner loop through staged provider readiness,
the full 1200-second simulated deadline, RUNNING without a port, terminal states,
invalid endpoints, watcher/owner loss, slow reads/acknowledgements, log failures
and a deliberately stalled log reader. Canaries verify that free-form provider
fields and log text cannot enter retained/public observations. Concurrent
Actions controls additionally use the actual owner/watcher loops, HTTP state
adapter and a real CPU child for delayed readiness and timeout-before-spawn.
Fixture durations are shortened only in these concurrent controls.

The source binding now covers 77 operational files, including the new helper
and its tests. The historical 75-file receipt is intentionally not rewritten:
it must reject this changed source before any create. A future paid scope would
still require a complete renewed qualification and a separate authorization.

Linux CI results are recorded in the Draft PR. Local targeted checks passed;
the full local run retains the known foreign-procfs failures, reported separately
from Actions. CPU preflight passed. GPU startup/inference/task execution remains
NOT RUN for this correction. No claim reset, paid/watch branch movement or
additional allocation is part of this work.

This improves early stopping and diagnosis of the real missing boundary. It
does not establish why the deleted Pod failed to become ready or guarantee
future provider availability. The twenty-minute bootstrap limit is unchanged.
