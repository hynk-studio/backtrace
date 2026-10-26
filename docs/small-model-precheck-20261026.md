# Preparation before the physical GPU minimum

Owner request: **최소검증 전까지 진행해**. Date: 2026-10-26 KST.
Refs [BT-001](https://github.com/hynk-studio/backtrace/issues/1).
Base: Draft #34, `6a0afa9a7ab88a1d77edc808bb78575b96b0ae17`.

This stage prepares and qualifies free execution-management mechanisms. It does
not run the GPU minimum, allocate hardware, download full checkpoints, perform
pretrained inference or train. Every prior scientific/runtime/collector source,
the original 36-assignment baseline plan, historical receipt and consumed paid
claim remains unchanged.

## Concrete checkpoints

The first actual GPU checkpoint is now explicitly **hardware only**: zero full
checkpoint downloads, zero pretrained requests and zero training steps. Require
the pinned Python/CUDA environment, native Linux namespace permissions, explicit
exclusive GPU UUID, at least 24 GiB reported GPU memory and native BF16. Repeat
the original input-only boundary tests and matrix/SDPA kernel controls.

The prepared active-context diagnostic allocates CUDA tensors, runs synchronized
matrix operations, requires one externally observable GPU context, and interrupts
the coordinator by deadline or parent death. Each interruption must be followed
by an idle inventory and successful fresh isolated kernels. It does not inject a
driver fault or prove which individual kernel was executing at signal delivery.
All positive NVIDIA branches remain NOT RUN. Failure stops the checkpoint; no
GPU reset, alternative device or model fallback is attempted.

Full E2B/E4B measurement is a separate later scope. Its original 36 assignments,
36 separate random diagnostics, tokenizer/model/runtime pins, generation policy
and evaluator are unchanged. The wrapper checks effective available memory before
entering the earlier `run-existing` implementation. The earlier command itself
is preserved as historical source and is not an outer supervisor.

## Time, evidence and resource cleanup

`small_model_lifecycle.py` accepts an exact existing resource identity and the
**original allocation-request timestamp**. Elapsed startup/setup time is deducted
before any command begins. Wall-clock and monotonic limits are both enforced;
clock reversal fails. Proposed limits remain 3,000 seconds total, with work
stopping by elapsed 2,580 seconds, up to 120 seconds for result recovery/export,
and 300 seconds for resource cleanup. This reserve tightens the prior informal
900+1,800+300 split; it does not extend the total window or promise full coverage.

The trusted setup/coordinator command runs in an outer PID namespace. Parent
death and namespace-PID-1 termination kill detached descendants, including the
existing inner model jails. Model input isolation still comes from the unchanged
collector. The supervisor requires a fresh acknowledgement from a separately
started local watcher before beginning work. Both retain the bound resource ID
and name for cleanup even if the local journal becomes unavailable.

The export child runs under its own finite deadline after work stops. It recovers
fsynced interrupted ledgers without rerunning requests, retains raw outputs and
missing assignments, and creates an owner-private tar with per-file hashes.
Only explicitly selected result/ledger/diagnostic names are eligible. Prompt,
job, checkpoint and private directories are excluded; links, oversized files and
changed files fail. The archive is not automatically uploaded. An export failure
must not prevent resource cleanup or be reported as successful evidence delivery.

The cleanup-only adapter calls the existing bounded Runpod v2 wire client. It
has **no create capability**. Complete list and exact-ID reads must agree on the
bound name/ID. A successful DELETE response is only an acknowledgement: two
subsequent independent observations must establish absence. Failed or conflicting
reads remain UNKNOWN/UNRESOLVED. Other resource IDs are not deleted. Provider
outages and bounded in-flight requests can still prevent cleanup by the proposed
deadline; no financial hard cap or guaranteed provider availability is claimed.
An already expired window refuses all work but still attempts bounded emergency
cleanup. That attempt is explicitly marked late; elapsed time never grants a new
work window and never excuses leaving an owned resource running.

The journal is local, and the watcher is a separate process on the same host.
This does **not** establish resilience to loss of that entire host. Deployment of
an independent remote watcher, allocation/create handling and delivery of this
new payload to an actual provider remain outside the qualified local mechanism.
No old controller is silently repointed to the new experiment.

## Effective memory

The new reader resolves `/proc/self/cgroup` against the cgroup-v2 mount and checks
each visible ancestor's `memory.max`, `memory.high` and `memory.current`, together
with host `MemAvailable`. Both throttling and hard-limit headroom constrain the
conservative estimate; swap is not counted as usable RAM. v1, ambiguous mounts,
path traversal and hidden ancestor limits fail rather than silently substituting
physical host RAM. A namespaced cgroup root needs host-side inspection.

The hardware-only checkpoint requires 8 GiB available RAM and 16 GiB free disk.
The subsequent full baseline still requires 32 GiB available RAM and 64 GiB free
disk before weights/copies. These are instantaneous observations, not reservations
against other jobs. The native CI host's actual memory observation is retained
even if it is below the full-model requirement.

## Free qualification and remaining gate

The new native workflow runs the complete repository suite, preflight and the
same pinned CPU runtime/input reconstruction. It then exercises real processes
and the real cleanup wire client against a loopback provider replica. Cases
cover success, worker failure, deadline, owner death, watcher death, journal loss,
failed export, false/lost DELETE acknowledgement, insufficient/expired time and
failed provider reads. A further connected case places the unchanged actual
tokenizer/random-model/oracle/failure-recovery pipeline under the new outer
supervisor. An outer-timeout case interrupts that real collector after its first
response and checks recovery of one received, one interrupted and 34 unrun
assignments, with disposable asset cleanup. Replica observations are not actual Runpod results.

The first native run, 40345716399 at
`d5e69339be192f2d972133d93d8a59b6a9e00e1c`, passed all 618 tests and preparation,
then failed a lifecycle assertion in the lost-DELETE-acknowledgement case. The
owner had already stopped with ValueError; both cleanup observations still
proved deletion. The first report did not retain its exception frames, so its
exact throw site is not claimed retrospectively. An independently reproduced
reader defect rejected a valid opened heartbeat inode when atomic replacement
reduced its link count to zero. The mutable-heartbeat reader now accepts that
complete old inode while retaining no-follow, private-owner and size checks;
immutable records retain the stricter rule. Exception frame locations are now
retained and deadline controls require the actual TimeoutError, not any failure.

The final focused local 16 tests pass. Full local runs and exact-source native
qualification are recorded separately in the final receipt. The failed native
archive is retained with digest
`f268eb8bffa270afe4a5d45696d8fb83ca6c64afcf7eeecfbf60ecf6d23a5251`.
No native or GPU success is inferred from unit-test counts.

Before an actual allocation, select a suitable native/privileged environment,
qualify the new payload's bootstrap/remote transport and independent remote
watcher, obtain a fresh authenticated price/stock/balance observation, and bind
one explicit current authorization to the exact qualified source. The conditional
USD 0.90 compute + USD 0.10 other ceiling and USD 0.50 credit reserve are proposals,
not live quotes or permits. The machine-readable plan deliberately reports
`PREPARED_EXECUTION_DISABLED` and a blocked launch gate. All prior paid scopes
remain consumed. GPU minimum, pretrained baselines, training, Augnes use and
Kaggle submission remain NOT RUN.

Primary references inspected 2026-10-26 KST:

- [Linux cgroup-v2 documentation](https://docs.kernel.org/admin-guide/cgroup-v2.html)
  for hierarchical limits and current/high/max semantics.
- [Runpod API v2 overview](https://docs.runpod.io/api-reference-v2/overview)
  for the v2 surface; this stage reuses the existing wire adapter and never calls
  a live create/delete endpoint. Free replicas establish only adapter/control behavior.
