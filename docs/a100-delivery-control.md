# Private delivery and external cleanup preparation

This is free CPU preparation for the existing conditional A100 attempt. It does
not allocate a Pod, fund an account or enable the private driver's GPU entry.
The owner has no RunPod account. Actual provider expiry, SSH, deletion and billing
remain NOT RUN; CPU fixtures are not provider qualification.

## Fixed private streams

`python3 -m tools.a100_delivery <kind> <source-root> <new-manifest>` verifies
the actual selected bytes before writing a private, no-overwrite manifest.
Kinds are `wheels`, `driver`, `task`, and `model`:

| Stream | Selection |
| --- | --- |
| wheels | Exact 246-wheel inventory; 5,373,559,590 bytes; unchanged approved closure |
| driver | Fixed prepared private driver plus 15 explicit workload support files |
| task | Seven frozen generation-side inputs plus original acquisition receipt; 222,386,501 bytes |
| model | Original v2 manifest's eight files; 23,297,590,856 bytes; no new model download |

The original task receipt was observed again on the authenticated Kaggle CPU
mount: 1,778 bytes, SHA256
`b6517713cc1eaf5bf3d341f5979f72b5eb7482de87b588ceb2c090139c8c67e8`.
Its records contain acquisition metadata for the seven selected inputs, not
evaluator-only answers. The seven existing input hashes, candidate, private
driver and model remain unchanged. The frozen metadata is read by exact hash;
the builder never enumerates arbitrary private files into a payload.

`tools/private_delivery.py push` streams over SSH with an independently
authenticated host key, strict known-host checking, no agent forwarding, a clean
child environment and a timeout bounded by remaining setup time. The owner must
obtain the host key through an authenticated provider channel; `ssh-keyscan`
alone is not identity verification. API/Kaggle credentials never enter a stream.

The standalone receiver checks the separately supplied manifest hash, storage
space, exact ordered file list, size and SHA256; rejects links, traversal,
truncation and extra files; then reopens and rehashes the written files before
an atomic rename. Failed transfers leave no committed destination. The sender
compares the receiver's receipt with its own manifest. A received directory is
private staging, **not an activated agent input mount**. Its delivery manifest
must remain owner-side when the future launcher constructs the exact logical
input paths and verifies UID/read-only isolation.

`a100_task.prepare` now copies an explicit workload-tool closure. It excludes
owner delivery/controller modules instead of sweeping future tools into the
worker directory. The generated `one_task.py` itself retains SHA256
`58880d27069574d10f60e90d3c80cbae89d080a4ed813206a973b49e6982ead2`;
its GPU/agent entry remains blocked.

## One-attempt controller and independent watchdog

`tools/runpod_control.py` has a library integration seam, not a rental CLI.
Its public CLI offers only private journal status and external watchdog resume.
The future launcher must run the watchdog on a durable, independent owner host
and produce a private heartbeat; a notebook session is not a qualified watchdog
host. No API key belongs on the agent Pod.

- Exact fresh authenticated offer: Secure Cloud, EU-RO-1, full A100 80GB PCIe,
  one GPU, on-demand, 100GB container disk, no persistent/network volume,
  at least 8 vCPU/117GB RAM, pinned base, no automatic top-up.
- Decimal cost calculation includes compute, disk, tax and other charges.
  It requires existing credit and at most $2 for 3,000 seconds. Test prices are
  fixtures, not authenticated stock/quotes or actual tax/billing evidence.
- An exclusive, fsynced owner-only journal consumes the single attempt before
  sending create. Restart/lost acknowledgement never issues another create;
  exact random attempt-name reconciliation binds only the owned Pod.
- Native UTC stop at request +2,880s and terminate at +3,000s are included in
  the same GraphQL create. Independent expiry readback must match both times
  before work. Useful work ends by +2,700s, leaving cleanup margin.
- A missing/stale heartbeat, incomplete launch, clock rollback, deadline,
  budget projection or changed resource triggers cleanup. Stop failure still
  attempts exact-ID deletion. Two consecutive exact-GET-absent and
  account-list-absent observations are required to call it deleted.
- STOPPED state, DELETE acknowledgement, transient API errors and an empty list
  after ambiguous creation are not deletion evidence. Slow cleanup counts
  toward request-to-deletion time. Unconfirmed cleanup remains an explicit
  failure; actual billing must be checked separately. These controls do not
  promise a financial cap through arbitrary provider/network outages.

## Provider-native expiry is still a hard blocker

Primary text checked on 2026-10-17 UTC:

- [RunPod GraphQL spec v1.1.0](https://graphql-spec.runpod.io/) documents
  `stopAfter` and `terminateAfter` as `DateTime` on
  `PodFindAndDeployOnDemandInput`. The published `Pod` response type does **not**
  list corresponding readback fields. Input-schema presence alone is insufficient.
- [REST create](https://docs.runpod.io/api-reference/pods/POST/pods) does not
  document these expiry fields. The current official
  [runpodctl create source](https://github.com/runpod/runpodctl/blob/e12397351fa126394ad04910ec6551351d164f01/internal/api/podcreate_v2.go)
  also omits them from the REST request mapping. Do not substitute advertised CLI
  flags or a shell `sleep` for provider-side persistence evidence.

The client first performs read-only authenticated schema inspection. If it
cannot establish a queryable expiry contract, it refuses **before create and
before consuming the attempt**. The field names in the guarded readback query
are conditional, not a claim that the current provider supports them. If the
authenticated API matches the published response schema, this path will block.
An official alternative readback path would need implementation and verification;
the existing approval is not silently weakened to external timers only.

## Validation status

CPU fault-injection and private stream results are being recorded for this
revision. They cover real separate sender/receiver processes and a fresh
watchdog process speaking to a loopback HTTP provider fixture. They do not
qualify live RunPod creation, native expiry, internet SSH or final billing.

Remaining deployment work is concrete: authenticate provider-native expiry
readback without allocating; establish a durable owner watchdog host and SSH
host identity; connect delivery staging to the frozen read-only input paths and
actual Pod isolation; then verify current authenticated offer/stock/tax/credit.
Until these gates pass, keep GPU entry blocked and payment on hold. No duplicate
GPU approval or intermediate merge is needed.
