# Prepaid A100 execution preparation — current status 2026-10-19

> **CURRENT FOLLOW-UP: [small-request transport qualification](a100-small-bootstrap.md).** The first funded create request failed because its inline transport exceeded the documented size limit. The follow-up replaces that delivery path and records current CPU preparation. The consumed journal is preserved; these historical readiness statements do not authorize a retry. See the [first-create report](a100-first-create-attempt.md) and [evidence](a100-first-create-evidence.json) for the original failure.

The rest of this document records the earlier preparation and observations.

This is the current amendment to the [2026-10-17 audit](a100-prepayment-audit.md).
The audit's observations remain valid history. The owner chose a single USD 10
wallet with automatic top-up disabled, USD 8 cumulative early stop and external
cleanup instead of waiting for unsupported provider-native timers. The first
experiment remains one allocation/server/task and 3,000 seconds. See the exact
[policy](a100-prepaid-policy.json). This is not authority to fund the account,
create access without the required browser confirmation, or run additional jobs.

## Implemented connection

- `tools/runpod_control.py` now uses the documented REST v2 create/get/list/action/
  delete contract, nested resource fields, all cursor pages and exact-ID cleanup.
  Unsupported timer fields are absent. The journal is fsynced before the one
  create; an ambiguous result is reconciled, never automatically recreated.
  Both exact GET and the complete account list must confirm absence twice.
- Cost checks include compute, temporary disk, tax, other attributable costs and
  consumption before this experiment in the USD 10 wallet. The USD 8 threshold
  includes a five-minute projection. Setup/heartbeat/workload/deadline/price or
  scope failures trigger stop and delete. No absolute financial cap is claimed.
- `tools/ssh_bootstrap.py` supplies a privately built, hash-pinned static Dropbear
  2026.94 server in the create request. This supports the exact public PyTorch
  base without a registry, apt/network installation or new serving dependency.
  Password/PAM authentication and forwarding are disabled. Account-wide SSH key
  registration is unnecessary. The owner generates the server key in advance;
  strict SSH identity checks compare that known key, not an unauthenticated scan.
  All environment values are removed before sshd except explicit non-secret
  PATH/HOME/LANG/LD_LIBRARY_PATH/CUDA_VISIBLE_DEVICES values. The server's private
  host key belongs only in root control storage; the owner client private key and
  provider API key never enter the Pod. The provider retains the create inputs.
- `tools/pod_bootstrap.py` reopens/rechecks received bytes before activation,
  removes transport metadata from logical model/task inputs, and makes them
  root-owned and read-only to the agent. This is a filesystem permission boundary,
  **not a claimed read-only bind mount or a need for privileged containers**.
  The unchanged offline installer runs from the delivered exact lock. Its venv
  is created directly at `/opt/backtrace-runtime` for the task UID, preserving
  absolute console-script paths instead of relocating the installed environment.
- `tools/runpod_job.py` connects external owner preparation, same-Pod SSH,
  sequential source streams, offline activation, one expiring root-only run
  permit, the frozen private driver, bounded receipt retrieval and cleanup.
  A separate worker refreshes an atomic private heartbeat; its failure leaves
  the owner watchdog running. A complete host outage remains the wallet fallback.
  Free Kaggle CPU is the intended owner host, with the model read from its fixed
  read-only mount and wheels staged separately. No simultaneous 29GB local copy
  or additional paid controller/storage service is required by this design.
  The observed session has accelerator **None**, internet on, the original
  2026-10-03 CPU environment and **Files only** persistence. Attempt state is
  fixed at `/kaggle/working/backtrace-a100-owner-state`; changing it is rejected.
  Files persistence supports normal interactive-session recovery, not a claim
  of synchronous journal survival through every host outage. Missing state
  requires reconciliation, never a replacement experiment.
- SSH bootstrap commands use bounded stdlib compression below the pinned
  server's 9,000-byte command limit. Receipt manifests travel over stdin, so
  their size cannot silently turn into an oversized command argument. Strict
  host verification, exact stream hashes and forwarding restrictions remain.

The generated private driver preserves all checked frozen prompt/agent/input/
isolation ASTs. Only its owner-controlled entry can consume the expiring permit;
reusing it or starting late/with changed driver bytes fails. CPU prerequisites
remain available without any permit. Untrusted UID code cannot enter root main.
The selected input, model, candidate and 246 wheel pins are unchanged. Two exact
runtime recipe documents were added to the explicit workload support closure;
owner control/delivery scripts remain outside it.

## CPU evidence

The final source snapshot passed **150/150 tests** and CPU preflight on free
Kaggle CPU. An actual loopback SSH transfer of the 18-file private workload
passed in 1.570 seconds, including receiver rehash, strict pre-generated host
identity, refusal of a wrong host key, absence of the fixture API credential
from the server environment, and owned daemon/key cleanup. Loopback measures
transport correctness, not the future internet bandwidth or GPU host.

Earlier checks exposed and corrected two transport issues: compiler/glibc build
differences caused the expected binary-hash refusal; the initial long receiver
command exceeded Dropbear's limit. The accepted Kaggle build uses the same
pinned official source and explicit build options, GCC 13.3.0-6ubuntu2~24.04.1
and glibc 2.39-0ubuntu8.9. Its two binary hashes are pinned in source. No unknown
binary was executed after a failed hash check.

Cloud ran the same 150 tests: 138 passed and 12 hit its existing foreign-procfs
lifecycle limitation; CPU preflight is READY. Its zero effective capabilities
also prevent SSH command execution after authentication (`setgroups` fails).
These are not called a full Cloud pass. No provider authentication or paid path
is exercised by the unit suite or local HTTP fixture. Exact executed hashes,
offline qualification and retained failures are recorded in the paired JSON.

All **246 frozen wheels / 5,373,559,590 bytes** were reacquired and rehashed.
The fresh, no-index/hash-required install passed dependency resolution,
`pip check` and the real serving/harness imports in **397.491 seconds** on free
CPU. No model was executed. The first private-driver CPU check then correctly
failed because the fixture venv referenced the owner-private portable Python
directory. The runtime was rebased to public `/usr/bin/python3.12` (Kaggle
3.12.3), keeping the complete installed package inventory unchanged and the
private owner directory closed. The production bootstrap already constructs
the venv with public `/usr/bin/python3.12`; it needed no source change. Existing
fixture scratch/receipt paths were preserved before retrying the CPU-only
check, leaving the driver's no-reuse guards intact.

That check then exposed a real missing dependency of **nested** sandbox venv
creation: the base's Python has no `ensurepip`. The outer installer already
handled this; the actual unchanged harness also invokes ordinary `venv` inside
the dropped-UID process. `pod_bootstrap` now installs a small, root-owned seeding
shim only when ensurepip is absent. It implements the standard venv seeding CLI
using the **same frozen pip 25.0.1 wheel**, exact hash lock, no-index/no-deps and
network-denying audit hook. It refuses a base-environment target or a pre-existing
different ensurepip; it is not a general replacement for the ensurepip API.
No official harness files or dependency versions are patched.

After this fix, the actual prepared private driver passed `--cpu-prerequisites`
in **14.972 seconds** on public CPython 3.12.3: UID 65534 / no-new-privileges,
unreadable parent environment/canary, failed account API access, actual nested
SubprocessManager creation and dependency inheritance (task Starlette 0.48.0,
pdm-backend 2.4.9, swegemma 0.2.7 and google-adk 1.36.1). It reported zero owned
survivors and removed scratch. No model start, inference or task generation ran.
The final source's 39 tool/test hashes matched the executed Kaggle snapshot.
Its full suite passed 150 tests in 30.692 seconds (31.074 seconds including the
wrapper). The final runtime-path adjustment leaves the same 18-file private
workload manifest byte-identical to the CPU-qualified workload.

The owner plan is READY: driver 18 files, wheels 246, task 8 and model 8, totaling
**280 files / 28,893,831,958 bytes**, all verified in place. No model duplication,
attempt marker or provider client was needed. The private draft was aligned
with the qualified source; no saved Kaggle version was created. Files only
remains selected, and the editor confirmed **off (run a cell to start)** after
the free CPU session was stopped. The original saved version remains 3.

## Running without advance spending

The following are operator commands, not shell work required from the mobile
owner. `prepare` verifies source files in place and produces private manifests;
it has no provider API client or allocation operation. Its config contains only
exact local driver/wheel/task/model and SSH paths plus the external owner host.

    python3 -m tools.runpod_job prepare <private-config.json> --output <new-private-plan-directory>

Only after owner funding, credential linkage, free preparation and a fresh
authenticated offer does the operator use the paid command:

    python3 -m tools.runpod_job run <private-plan-directory> --offer <fresh-private-offer.json> --api-key-file <private-owner-key-file> --state-directory <fixed-private-attempt-directory>

The same fixed attempt directory is retained for recovery; do not replace it
to obtain another run. Resource creation has no automatic retry or hardware/
region fallback. A stopped Pod is not a deleted Pod. Billing remains pending
until separately observed. Capture minimum receipts before deleting early on
success or failure; skip optional public verification rather than extend time.
All four streams are rehashed before the attempt marker and allocation request;
slow first reads from Kaggle model mounts therefore happen on the free CPU
owner host before any GPU allocation.

## Remaining live boundary

New RunPod access must be approved and connected through protected owner storage,
never pasted into chat or included in the notebook source. The notebook's CPU
source/tests are private; no new saved version or public sharing is necessary.
The inspected key-creation UI offers management GraphQL Read/Write and inference
API permissions separately; it does not expose a Pod-only management grant.
The prepared, **unsubmitted** key form enables management Read/Write and leaves
`api.runpod.ai` disabled. This is broad management access, not a least-privilege
Pod-only claim. Creation and protected storage in the private Kaggle owner
notebook's Secrets require the owner's action-time confirmation. No key was
created, copied or transmitted in this preparation.
After linkage, use read-only provider checks before asking for the one top-up.
The billing page was also inspected: balance USD 0.00, current spend USD 0.000/hr,
Auto-Pay disabled and no payment methods. Selecting Other and entering `10`
left Pay with card enabled. The button was not clicked; no card, payment method,
checkout tax or final charged amount was entered, saved or accepted.
The live Secure / EU-RO-1 quote then showed one A100 PCIe 80GB available, with
125GB system RAM / 16 vCPU. The draft applied the exact digest-pinned image,
100GB temporary disk, no persistent volume, no Jupyter or automatic SSH, and no
HTTP port. GPU USD 1.79/hr plus disk USD 0.014/hr totals USD 1.804/hr (UI rounds
to 1.80), or about USD 1.50 for 50 minutes **before tax/other costs**. Deploy Pod
was not clicked. Stock was not reserved; this is not the fresh authenticated
API offer required by the controller.
Exact stock, prices, tax and credit are volatile execution-time facts. No
alternative GPU/region is implicitly authorized when PCIe/EU-RO-1 is unavailable.

The private driver's retained `provider_expiry_seconds` telemetry name is
historical. It records the intended 3,000-second allocation envelope and is
not evidence that a native provider timer exists or was accepted.

Actual provider create/readback, internet SSH bandwidth, assigned hardware/MIG/
driver/capabilities/isolation, full 23GB model transfer, serving health, returned
model request, task/patch, deletion and final billing remain **NOT RUN** until
the single approved allocation. These are observations of that attempt, not a
request for another paid trial before it. No funding or GPU request occurred in
this preparation. The PR stays Draft, Issue #1 stays open, and no merge is needed
to carry out the already scoped experiment after its prerequisites pass.

## Primary interfaces inspected

- [REST v2 migration](https://docs.runpod.io/api-reference-v2/migrate-from-v1)
- [Create](https://docs.runpod.io/api-reference-v2/pods/create-a-pod),
  [get](https://docs.runpod.io/api-reference-v2/pods/get-a-pod),
  [list](https://docs.runpod.io/api-reference-v2/pods/list-pods)
- [OpenAPI bytes](https://api.runpod.io/v2/openapi.json): 274,963 bytes,
  SHA256 `fe8a74b177282ec89a9ba1c75d3ce1d4bd1a2a9b9609fbdb4bd131d5b4a24506`,
  reacquired during this preparation; no authenticated API mutation.
- [Billing](https://docs.runpod.io/accounts-billing/billing): zero-balance
  termination without network volumes; five-minute settlement, no guaranteed
  exact spending cutoff.
- [Dropbear source](https://github.com/mkj/dropbear/tree/DROPBEAR_2026.94),
  privately acquired immutable-hash archive and static build, separate from the
  scientific serving wheel inventory. Original release-host access returned
  HTTP 403 in this executor; official GitHub source succeeded. No GPG signature
  verification or third-party binary redistribution is claimed.
- Python [venv](https://docs.python.org/3.12/library/venv.html) and
  [ensurepip](https://docs.python.org/3.12/library/ensurepip.html): standard
  nested venv creation seeds pip by default; the pinned bootstrap supplies this
  missing base capability without network package resolution.


## Resumption checkpoint — 2026-10-18T15:03:05.087Z

The replacement session recovered the existing private Kaggle draft and its
Files-only working data. It did not rerun the acquisition/bootstrap cells or
consume a provider attempt.

- The current source is selected by the private `qualified-code-root.txt`
  marker under `qualified-source`, not the older `source` preparation tree.
  All 39 tool/test SHA-256 values and the frozen private driver hash match
  the published qualification evidence. The four manifest hashes match;
  all 280 listed files / 28,893,831,958 bytes are present and size-checked.
  This is not a new full-content hash of the large model/wheel files; the
  existing paid entry must rehash all four streams before any create.
- The restored owner-plan/SSH directories were 0755 and their private files
  0644, while the enclosing preparation directory remained 0700. The private
  draft now includes a CPU-only recovery cell that refuses symlinks/foreign
  ownership, restores 0700 directories and 0600 exact owner files, selects the
  qualified source, verifies the hashes and confirms no attempt journal.
  It passed with `RECOVERY_READY`. Run it after session recovery, before
  credential use. No keys were regenerated and no security guard was relaxed.
- In this replacement Cloud executor,
  `python3 -m unittest discover -s tests -p test_runpod_control.py -v`
  passed 29 tests and the corresponding `test_prepayment_job.py` invocation
  passed 13 tests. CPU preflight is READY. These 42 focused checks do not
  replace or count as a new run of the prior Kaggle 150-test qualification.
- Fresh account UI showed USD 0.00 balance, USD 0.000/hour spend and Auto-Pay
  disabled. With EU-RO-1 selected, the A100 PCIe 80GB card displayed
  **Out of capacity**. No alternative GPU/region was selected. This volatile
  UI observation is not a qualified authenticated API offer or a reservation.
- Automatic browser approval review rejected the Create API Key button action
  as creation of powerful new account access. It was not bypassed. New key
  creation and protected linkage to this private notebook's Secrets await
  explicit owner confirmation; authenticated provider API checks and tax/
  final cost verification remain NOT RUN. Funding and GPU creation remain
  NOT RUN. The free CPU session was stopped and the draft is saved;
  saved notebook version remains 3.

Next action: obtain confirmation specifically for RunPod management Read/Write
key creation and private Kaggle Secrets storage, with inference permissions
left disabled, then complete read-only provider checks. Do not fund or allocate
while the exact authorized offer is unavailable. The existing one-allocation,
one-server, maximum-one-task, 3,000-second and USD 8 cumulative early-stop
policy remains unchanged. PR #7 stays Draft and Issue #1 stays open.

## Approved credential linkage and authenticated read-only check — 2026-10-19 KST

The owner explicitly approved the pending RunPod management Read/Write key
creation and storage in this existing private Kaggle notebook's Secrets.
The created key uses Restricted settings: management GraphQL Read/Write,
inference `api.runpod.ai` None. This remains broad account management access;
it is not a Pod-only grant. The notebook links only
`BACKTRACE_RUNPOD_API_KEY`; the existing unrelated secret remains unselected.
No provider key was placed in notebook source, Git, a working file or the Pod.

An initial unused key value appeared in a browser-tool error diagnostic.
That key was immediately **disabled**, with Disabled / Never used readback,
before any linkage or API use. It was not stored in Kaggle Secrets. A replacement
with the same approved permissions was created, stored without printing its
value and used for the checks below. There is one enabled replacement key and
one disabled unused key; disabling is not claimed to be permanent deletion.

The free CPU recovery cell passed again before credential use: 39 qualified
source hashes and the fixed private-driver hash match, owner files have their
protected permissions, the 280 listed inputs remain present and size-checked,
and the fixed attempt journal is absent. This does not add a new full hash
verification of the large inputs or rerun the earlier 150-test suite.

At **2026-10-18T16:07:03Z** (2026-10-19 01:07 KST), the private notebook retrieved
the key through Kaggle Secrets and performed only read operations:

- The qualified REST v2 client completed the paginated Pod-list contract:
  **0 Pods / 0 earlier Backtrace Pods**. No create/action/delete request was sent.
- The authenticated catalog GET returned HTTP **200**, 383 bytes for exactly
  `NVIDIA A100 80GB PCIe`, Secure, one GPU, Romania and minimum CUDA 12.8.
  Availability was **NONE**, with no `EU-RO-1` datacenter entry. The Secure list
  compute price was USD **1.79/hour**. This is neither a stock reservation nor
  the complete disk/tax/resource-qualified execution offer.
- The authenticated latest billing bucket GET returned HTTP **200**, 466 bytes:
  0 records and totalAmount 0 across the returned resource categories.
- A read-only GraphQL account-schema introspection returned HTTP **400**.
  No account balance/tax fields were obtained through GraphQL; this is retained
  as an unsuccessful probe, not an API-verified balance or tax result.
- The account billing UI separately showed **USD 0.00 balance,
  USD 0.000/hour current spend, Auto-Pay Disabled and no payment methods**.
  Checkout tax and the final all-in offer remain **NOT VERIFIED**.

The sanitized read-only result is retained under the existing private evidence
directory and in the notebook's draft output. Only the secret label is in
source; the credential stayed in local function memory during the read calls.
The free CPU session was stopped with **Session stopped / off** readback,
the draft was saved, and saved version remains **3**. No new saved version,
training, model start, task, submission, merge or issue closure occurred.

**Funding 0 / GPU allocation 0 / provider attempt unconsumed.** Do not fund or
allocate against unavailable stock. Next: recheck the same authorized
Secure / EU-RO-1 / A100 80GB PCIe offer when work resumes; only if its stock,
resources, final cost and all other existing gates pass should the owner
complete the one USD 10 top-up. No alternative GPU/region, automatic retry,
additional funding or recurring stock-monitoring task is authorized here.

