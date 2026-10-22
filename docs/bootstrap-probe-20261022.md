# One minimum boot and connection diagnostic

The owner instructed **진단 실험부터 하자** after the assessment that another
full task run was not yet justified. This authorizes one new minimum diagnostic
allocation under `owner-bootstrap-probe-20261022`; repeating the same instruction
does not grant a second allocation. Review branch `bt-001-bootstrap-probe` is
based on Draft PR #11 at `a673cd92d8ba2fbd58f90d78401a205dade7f7b5`.

## Experiment

Use the unchanged digest-pinned PyTorch image, A100 80GB PCIe x1 Secure,
100 GB temporary disk, no persistent/network volume and the same reviewed
mutual-TLS-to-pinned-SSH initializer. No model, wheels, task inputs, inference,
server or competition execution is transferred or started. Keeping this
deployment boundary unchanged makes this experiment relevant to the prior
readiness failure.

Observe provider lifecycle and direct TCP mapping separately. Sample the actual
read-only log API during the wait and immediately before cleanup, retaining
bounded safe signatures/counts and explicit failures. Publish a strictly
allowlisted observation in this new namespace at most once a minute. If ready,
transfer the pinned SSH executable once, verify its host identity, execute a
small clean-environment Python command and query the actual GPU with nvidia-smi.
Then delete the Pod; no automatic progression to model/task execution.

| Observation | What it establishes |
| --- | --- |
| PROVISIONING/STARTING without RUNNING | Provider/container readiness remains incomplete |
| RUNNING without direct endpoint | Direct mapping is the remaining readiness boundary |
| Log API HTTP success or numeric failure | Actual log-read capability, independent of assumptions from the schema |
| TLS transfer failure | Initializer/port/authenticated-transfer boundary, not model startup |
| SSH or remote probe failure | Pinned SSH/command/GPU observation boundary |
| TLS, SSH and GPU observation pass | Minimum boot/connectivity works for this one allocation; model/task still untested |

## Limits and separation

Existing USD 10 wallet and USD 8 cumulative stop remain. No funding or Auto-Pay
change. Hourly compute plus temporary disk must not exceed USD 1.804. The
30-minute allocation-inclusive bound gives at most USD 0.902 at that rate,
subject to the existing external-controller limitations. The previous observed
balance was USD 7.2408300035; a new authenticated read must refresh it.

Bootstrap readiness remains limited to 1200 seconds; diagnostic setup/useful work
to 1500 seconds; request-to-deletion target to 1800 seconds. Independent owner
and watcher retain exact-ID/name reconciliation and two absence reads. One
create only, including ambiguous create completion. No automatic paid retry.

Dedicated immutable actual-run branches are `bt-001-a100-start-bootstrap-probe`
and `bt-001-a100-watch-bootstrap-probe`. All earlier namespaces and paid/watch
heads remain unchanged. The fixed diagnostic profile uses these identities and
stricter deadlines, and restores the legacy defaults when used in CPU tests.
It does not reset or rearm an earlier scope.

## Qualification

This input-free experiment has its own source-bound qualification, rather than
pretending the full model/task receipt qualifies a different workload. Before
allocation require the whole current Linux suite, the full operational source
hash set, a fixed-hash transport rebuild, actual host mutual TLS/pinned SSH,
all seven concurrent lifecycle controls in the diagnostic namespace, and the
same initializer/transport/clean Python command inside the exact image on CPU.
The free workflow has no provider credential. Its successful run/report and all
bound file hashes must match; final receipt-source CPU must pass separately.

A separate read-only workflow refreshes account/stock and later verifies the
recorded exact Pod absence and final account state. Result metadata and private
ciphertext are retained separately; raw keys/initializers/source maps are never
uploaded. The historical 75-file full-task receipt remains unchanged and does
not qualify these changed files or any future model run.

No merge, recurring automation, additional funds, second allocation or hosted
submission is included. References #1. Actual execution results will be appended
after this diagnostic, with unknowns preserved.
