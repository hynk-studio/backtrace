# One hardware-only minimum (2026-10-27 KST)

The owner instructed **최소검증 진행하자** after Draft #37 qualified the ordinary
container CPU path. This stage permits at most one GPU allocation, without
checkpoint downloads, pretrained requests, training or Augnes changes. No
historical source, runtime lock, scientific input or consumed claim is modified.

The fixed limits are USD 1 projected additional spend, 3,000 seconds from the
allocation request, work stop at 2,580 seconds, a 120-second export margin and
300 seconds for cleanup. Existing credit must retain at least USD 0.50; no
top-up, account setting change or automatic allocation retry is allowed. The
provider is selected only from fresh authenticated secure on-demand quotes with
one GPU, 32 GB or more provider RAM, eight vCPUs, 100 GB container disk and no
persistent volume. Nominal 24 GB products are excluded because the earlier
unchanged hardware check requires at least 24 GiB actually reported. Only
40 GB or larger products are considered, within the same budget.

## Dedicated ordinary-container scope

The same digest-pinned image, exact Python 3.12.14, 56-wheel CUDA 12.6 closure,
mutual TLS bootstrap, pinned SSH transport and non-root syscall filter are used.
The original GPU UUID/driver/memory/BF16 matmul/SDPA checks remain unchanged.
The new standalone entry has no model, training or prompt command. It is designed
to exercise actual kernels, an externally observed active context, deadline interruption,
SSH loss and privileged supervisor loss. After each interruption it requires
worker PID/start-identity absence, idle device observation and fresh kernels.

Ordinary OCI is a distinct boundary from the earlier native bubblewrap runner.
Root-owned runtime and fixed worker UID/capability/socket/process denial are
rechecked on the actual instance. The earlier native namespace and memory
requirements are preserved, rather than described as passing in a container.

Visible cgroup limits and host MemAvailable are recorded. The hardware-only
entry additionally touches every page of an 8 GiB mapping, checks page residency,
RSS and zero swap, and then releases it. This is an instantaneous resident-capacity
observation. It does not establish hidden ancestor limits, a future reservation,
or the 32 GiB full-model admission requirement. No pretrained launch is enabled.
The free exact-image rehearsal uses only 64 MiB and explicitly rejects CUDA;
that observation is never presented as a physical GPU test.

## Independent cleanup and one-use state

Owner and watcher are different native runner jobs, with distinct kernel boot
identities, the same immutable source and a first-attempt workflow identity.
They use only the new minimum state branch. The watcher caches the random exact
resource name and immutable claim before it acknowledges that create may begin.
There is one non-idempotent provider create call. The returned Pod ID is bound to
the claim; owner/watcher retain cleanup identity when state or heartbeats fail.
Cleanup reuses the previously qualified bounded REST adapter and two independent
absence observations. An ambiguous create is never retried and remains under
cleanup-only observation. Provider outages may still leave cleanup unresolved;
these controls are not a provider-enforced financial cap.

The free distributed rehearsal creates a labelled resource in GitHub state,
lets the owner's real heartbeat cease, and requires the separate watcher to
remove that exact replica. It makes zero Runpod requests. This qualifies the
cross-runner state and cleanup decision path; actual provider deletion is an
observation of the separately authorized hardware attempt.

The paid start branch is inert without an externally recorded, source-bound,
expiring single-use authorization and a successful exact-source free workflow.
Old permits and claims cannot be read through the new state adapter. The main
review branch does not allocate hardware.

## Current observations

Read-only quote workflow 40447895250 at 9a0e5daddaa704dbac6a344a0f767a42ea3a7dd4
observed USD 3.0795030588 credit, zero hourly spend, autopay off and zero Pods at
2026-10-27 04:06:47–04:06:57 UTC. Eligible A40/A6000 48 GB stock was quoted at
USD 0.59/hour in several regions; those observations are not reservations.
The 100 GB disk projection is USD 0.015/hour, rounded above the official
USD 0.10/GB/month rate. The 3,000-second compute-plus-storage projection is
USD 0.5041666667. A fresh quote is required immediately before allocation.
See [official pricing](https://docs.runpod.io/pods/pricing), inspected 2026-10-27.

The first quote workflow 40447797771 did not create a job because an unquoted
inline pip command contained a YAML colon-space sequence. The corrected block
command passed. Both observations are retained; no provider mutation occurred.

The first two container runs (40448784125 and 40449227306) passed their full
native suites (648 / 650 tests) but stopped before runtime transfer because a
create-only pinned known-host file was initialized twice. Both owned CPU
containers were removed and confirmed absent twice. The second distributed
owner also discarded a successful cleanup observation by immediately reading
it again; that second read returned no record. The first immutable observation
is now retained, with an executable regression test. Bounded read confirmation
handles readback lag without blindly repeating a state write.

A queued source c3fc7f49db09bac66400ed65a6bee2eca90f3024 was superseded before
execution (run 40449409002). The latest source adds bounded EOF finalization
for a worker that has emitted its response and an actual allocation work alarm;
the latter interrupts blocked owner work before cleanup. Free distributed
watcher deletion has been observed on separate runner kernels. Full local
Work tests attempted 648 tests with the known 5 failures, 10 errors and 4 skips
in existing ensurepip/procfs/native-host paths; twelve focused final tests pass.
These local failures remain separate from the native qualification.

## Qualified source and actual one-allocation result

Source `bc4e691306f7eca3adcc52abf438a564716226b4` passed native run
[40449750336](https://github.com/hynk-studio/backtrace/actions/runs/40449750336):
651 tests in 173.449 seconds, with no failures/errors/skips, preflight, exact
Python/CUDA-package installation and all 16 free container checks. The three
real CPU interruption cases and separate-runner replica deletion passed. The
64 MiB resident probe and missing-GPU rejection are CPU evidence only.

The source-bound single-use authorization was recorded at state commit
`f05ea8c84c1be73931e284771297bb3ab255d643`. Paid run
[40450834812](https://github.com/hynk-studio/backtrace/actions/runs/40450834812)
made exactly one provider create call at 2026-10-27 04:40:25 UTC. Fresh quotes
selected one NVIDIA A40 48 GB in CA-MTL-1 at USD 0.59/hour, with the unchanged
USD 0.5041666667 maximum compute-plus-storage projection. The exact resource was
Pod `qxvxecldgw2ohg`, named
`backtrace-small-minimum-ba110d411173474dacf9772a187fe829`.

**The minimum failed before runtime transfer or GPU execution.** The owner
accepted the resource contract and saw RUNNING, then dereferenced
`pod['ssh']['direct']` before the endpoint metadata was ready. The retained
TypeError frames identify `owner` line 335 and `endpoint` line 160. They establish
a null intermediate at that line, but the raw response was not retained, so they
do not distinguish null `ssh` from null `direct`. There is no connected receipt,
kernel, GPU-context interruption, actual 8 GiB resident probe, pretrained request
or training result from this allocation.

Owner completion was recorded about 10.12 seconds after the claim. The delete
request followed about 13.16 seconds after the claim. Independent cleanup proofs:

| Controller | Absence observations, UTC | Result |
| --- | --- | --- |
| Owner | 04:42:09.011 and 04:43:39.611 | DELETED, two reads |
| Watcher | 04:42:06.962 and 04:43:37.670 | DELETED, two reads |

The controllers used distinct runner boot hashes and cached the same source,
claim and exact Pod identity. The original watcher reason is retained as
`RESOURCE_CHANGED`: after observing OWNER_DONE it checked the now-absent Pod and
overwrote the reason. This classification defect does not invalidate its two
absence observations; it is corrected below without editing the original record.

The final authenticated account observation at 04:43:41 UTC retained
USD 3.0795030588, zero hourly spend and autopay off; the complete inventory at
04:43:49 UTC contained zero Pods. Observed balance delta is zero, not a promise
of zero final billed charges. Both paid jobs terminated. The authorization is
consumed and the paid start branch remains on its original source.

## Free correction after the failed attempt

Source `a94cb50535a8c4d7107de32862d0e016c46d96bb` treats incomplete SSH/runtime
metadata as pending even when provider power state is RUNNING. It requires one
complete, valid and matching direct/runtime SSH mapping before launch, rejects
contradictory mappings, and fails if an established endpoint disappears or
changes. The original 900-second startup bound and allocation work alarm remain.
Allowlisted readiness observations record status and field presence without
addresses, environment variables or provider response dumps. OWNER_DONE now
retains its reason when the owner's deletion has already completed.

Seventeen focused local tests passed, including the actual owner state machine
with RUNNING-before-metadata, persistent pending startup, contradictory mapping,
endpoint loss and already-completed owner cleanup. These use simulated provider
snapshots and do not establish real provider connectivity. The corrected source
explicitly fingerprints the reused readiness observer, cleanup controller and
cleanup amendment; all 47 previously tracked sources remain unchanged.

Corrected-source native/container qualification run
[40452065045](https://github.com/hynk-studio/backtrace/actions/runs/40452065045)
passed all **656 tests in 189.165 seconds**, with zero failures/errors/skips,
preflight, exact offline runtime installation and all 16 container controls.
All 58 tracked source hashes match the exact commit. The 64 MiB resident probe
and three real CPU interruption checks passed. The owned container was deleted
and observed absent twice in 7.08 seconds. Separate native owner/watch jobs
again proved heartbeat-loss replica deletion with zero provider create calls.

The corrected local full suite separately attempted 656 tests in 143.287 seconds
with the same 5 failures, 10 errors and 4 skips in existing environment-dependent
paths; their names match the initial local failures. These do not replace or
invalidate the recorded successful native run. All 15 artifacts, including the
quote artifact, and all 71 archive members were independently hash-checked.
Eleven paid state blobs match the immutable Git tree; all 76 previous branch
heads and 47 previous tracked sources are preserved.

No second provider allocation is part of this correction. Read
`small-model-minimum-evidence-20261027.json` for final qualification results,
artifact/member hashes and preserved failures. Actual hardware minimum remains
**NOT PASSED**. E2B/E4B pretrained baselines, training and Augnes transfer remain
**NOT RUN**. A future paid attempt needs its own current source-bound scope;
the consumed authorization cannot be reset or reused.
