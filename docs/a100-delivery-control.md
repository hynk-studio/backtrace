# Private delivery and external cleanup preparation

This is free CPU preparation for the existing conditional A100 attempt. It does
not allocate a Pod, fund an account or enable the private driver's GPU entry.
The owner subsequently created and signed into RunPod. The
[prepayment audit](a100-prepayment-audit.md) supersedes the earlier account
blocker and records stronger negative evidence for native expiry. Actual
provider expiry, SSH, deletion and billing remain NOT RUN; CPU fixtures are not
provider qualification.

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
an atomic rename. Rejected payloads leave no committed destination. A lost final
acknowledgement is uncertain staging, never permission to start work. The sender
compares the receiver's receipt with its own manifest. A received directory is
private staging, **not an activated agent input mount**. Its delivery manifest
must remain owner-side when the future launcher constructs the exact logical
input paths and verifies UID/read-only isolation.

The real wheel rehearsal exposed three basenames of 105/112/115 characters
that cannot fit USTAR's unsplittable 100-byte name field. GNU long-name records
now preserve these exact names; manifest/path/type/hash enforcement is unchanged.
A regression test uses the actual longest filename with disposable fixture bytes.

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

**Later 2026-10-17 finding:** upstream runpodctl PR #330 removed both timer flags
because accepted deadlines were not enforced; restoration PR #331 closed
unmerged. Our live read-only request rejects both intended Pod readback fields.
The current REST v2 specification supplies no equivalent schedule. See the
[audit and exact evidence](a100-prepayment-audit.md); creating an API key alone
does not resolve this blocker. The conditional adapter below remains disabled
for real allocation. REST v1 is also scheduled for retirement on 2026-11-15.

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

The final tooling revision is `ed3d346b9fcdcd680f28a325b47686b66316c552`.
[Evidence JSON](a100-delivery-control-evidence.json) separates Cloud, Kaggle
and actual-provider status. All 35 executed tool/test source hashes match this
revision; later report-only commits do not change those tested bytes.

| Check | Observed result |
| --- | --- |
| Kaggle CPU / CPython 3.12.14 full suite | **132 PASS, 0 skipped**, 27.942s |
| Kaggle CPU preflight | READY |
| New fault/inventory cases | 42 cases: 14 stream, 24 controller, 4 frozen inventory; included in the full suite |
| Exact selected task stream, separate processes | Eight files / 222,386,501 bytes; rehash PASS, 6.187s |
| Exact runtime wheel stream, separate processes | 246 files / 5,373,559,590 bytes; rehash PASS, 144.856s |
| Real OpenSSH loopback, selected task bytes | PASS, 5.886s; wrong host key refused; owned server group 0; temporary keys removed |
| Real private driver stream on Cloud | 16 files / 269,695 bytes; rehash PASS, 0.523s; GPU entry still refused |
| Cloud full suite / preflight | 132 run, 12 existing foreign-procfs errors; preflight READY |

The controller tests include a fresh independent process that reads the durable
journal and drives the real HTTP adapter against a loopback provider fixture,
with no launcher heartbeat. They verify deletion/readback of the exact owned
fixture Pod while preserving an unrelated fixture Pod. This is **not** observed
RunPod deletion. Authenticated provider creation/expiry/delete/billing, internet
SSH, actual Pod isolation, model transfer/load and agent execution are NOT RUN.
Previous official-wrapper, full offline installation and pinned-base user-space
qualification results remain historical; they were not repeated or counted here.

The first notebook control script had a newline-escaping syntax error before
launching any subprocess. That source/error is preserved. The initial 131-test
suite passed, but the subsequent full-wheel stream rejected USTAR long names
and did not commit its destination. That failure, the three filename diagnoses,
and corrected-run evidence are retained. No source/runtime/input pin was changed
to make a failed check pass.

Fresh wheel acquisition took 134.868s with all 246 exact bytes verified. The
38 unchanged Kaggle wheels were selected by explicit mounted path; the three
approved replacements and remaining supplemental hashes were unchanged. This
run qualifies delivery of the closure, not a new offline installation. Model
manifest construction was checked but its 23GB payload was not downloaded or
transferred. Local throughput is not an internet/provider transfer guarantee.

The 86,483-byte Kaggle log/metadata archive was downloaded and its SHA256 and all
member hashes verified. The combined private continuation evidence was durably
saved: 47 members, 258,044 bytes, SHA256
`e9c6d105b674d297fb56c75d48acd4714e5efc68c088e7e4c7d53ff5cc090947`.
It retains the private prepared driver, initial failures, corrected scripts,
logs and receipts; excludes wheels, model weights, task payloads and credentials.
No durable wheel backup is claimed. The prior full wheel ZIP was not restored;
this turn used a fresh exact acquisition and removed both wheel source/copy after
verification. The saved acquisition recipe supports a later free rebuild.

All owned job groups were empty, ephemeral SSH keys were removed, temporary
Python/cache paths were removed, and Kaggle's **off (run a cell to start)** state
was observed. The saved Kaggle version remains 3; no version-save retry occurred.

Remaining deployment work is concrete: authenticate provider-native expiry
readback without allocating; establish a durable owner watchdog host and SSH
host identity; connect delivery staging to the frozen read-only input paths and
actual Pod isolation; then verify current authenticated offer/stock/tax/credit.
Until these gates pass, keep GPU entry blocked and payment on hold. No duplicate
GPU approval or intermediate merge is needed.
