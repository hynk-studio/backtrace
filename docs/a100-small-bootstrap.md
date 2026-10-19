# Small-request transport qualification — 2026-10-19

The owner requested preparation up to the GPU experiment. This follow-up
replaces the oversized inline SSH binary with a small authenticated receiver.
It makes no provider API call and creates no GPU resource.

## Delivery change

The create body contains a Python 3.12 standard-library receiver, a temporary
server TLS identity, the trusted client certificate and the existing SSH
identity. It contains neither the 1,400,320-byte executable nor the owner client
private keys. The external owner sends the unchanged hash-pinned Dropbear
2026.94 binary over mutual TLS 1.3 to the Pod's published TCP 22 mapping.
Only the exact length and SHA256 are accepted. The receiver then removes its
TLS files and hands the same port to the unchanged Dropbear daemon. The existing
strict SSH host check and four private file streams follow.

There is no artifact hosting service, third-party binary publication, package
download, extra port, account SSH-key registration or serving dependency change.
The API still retains the supplied server identities. Account credentials and
both client private keys remain on the external owner CPU host.

Preparation and the paid entry verify the local binary, private permissions,
certificate/key pairing and at least one hour of certificate validity before
source rehashing or provider authentication. Generated transport certificates
last seven days; expired material must be regenerated and requalified locally.
The exact serialized request still passes the independent 102,400-byte gate.
The receiver permits one authenticated transfer, bounded bytes and time.
The owner retries only TCP readiness, never an authenticated upload or create.
A bootstrap failure marks the worker failed before input transfer or task start;
the existing independent watchdog performs resource cleanup.

## Validation and prepared inputs

The actual complete create body is **5,577 bytes**, down from 863,192 bytes,
against the provider's 102,400-byte limit. Free Kaggle CPU passed **162/162 tests**
without skips and reported CPU preflight READY. The actual pinned binary was
delivered, the same port handed to SSH, and the frozen 18-file / 295,011-byte
driver transferred and rehashed in **2.464 seconds**. Wrong SSH identity was
refused, fixture account credentials and bootstrap variables were absent from
the remote environment, and the owned daemon and temporary keys were removed.
The same real transfer also passed on Kaggle's system `/usr/bin/python3.12`
in 2.486 seconds; this is not an execution of the RunPod image itself.

At **2026-10-19T08:21:17Z**, preparation completed a fresh SHA256 verification
of all **280 files / 28,893,831,958 bytes** in 228.080 seconds: driver 18,
wheels 246, task 8 and model 8. The four manifest hashes are unchanged. A private
plan and transport identities are prepared, and all 41 executed tool/test hashes
match the publication candidate. The actual prepared create body is also
5,577 bytes. These transport certificates expire on 2026-10-26 at 08:17:29 UTC;
the existing validity gate requires refresh before a later run if necessary.

Cloud passed all 8 new transport tests and all 46 focused controller/job tests.
Its full 162-test run retained 12 existing foreign-procfs lifecycle errors;
this is not reported as a full Cloud pass. The successful full suite and actual
SSH execution ran on the real root Linux PID namespace of free Kaggle CPU.

Final qualification and source hashes are recorded in
[a100-small-bootstrap-evidence.json](a100-small-bootstrap-evidence.json).
The standalone, free-CPU reproduction command is:

```sh
python3 -m tools.qualify_ssh_transport <private-pinned-build> <private-driver> <new-private-receipt.json>
```

This runs the literal initializer with only its private root and loopback port
substituted. It never executes the workload. The first rehearsal used a `/tmp`
destination, which the existing SSH delivery boundary correctly refused after
successful TLS transfer. That failure and cleanup receipt are retained. The
fixture was moved under `/root`; the production boundary was not weakened.

A free-session replacement lost this turn's uncheckpointed scratch changes.
The original consumed journal survived unchanged. The public source patch was
restored by exact hashes and final qualification rerun. This does not establish
durable survival through every owner-host outage. The unnecessary original
wheelhouse input was detached from the notebook to avoid repeating its slow
attachment; the actual frozen wheel path remains the separately prepared
private 246-wheel directory. The pinned model and selected-task inputs remain
attached. No saved notebook version or input asset was deleted or published.

The full tests additionally exercise missing client authentication, wrong
server identity, expired credentials, altered local binary, corrupt/truncated/
oversized streams, bounded connection failure, and worker failure before task
execution. Wrong SSH host identity and credential-free remote environment are
checked with the actual pinned daemon. Loopback is evidence of protocol and
handoff correctness, not a measurement of RunPod internet bandwidth.

## GPU boundary

The checkpoint, candidate, frozen driver, task, 246 wheel inventory, public
image digest, A100 PCIe 80GB / Secure / EU-RO-1 selection and spending/time limits
are unchanged. The controller still uses one allocation, one inference-server
start, at most one task, 3,000 seconds including setup and deletion, the existing
USD 10 wallet and USD 8 cumulative early stop with a five-minute projection.
Auto-Pay and additional top-ups remain disabled under the existing policy.

The first consumed journal remains byte-identical at the fixed state directory.
No journal reset, replacement attempt directory or automatic retry was added.
The prepared private plan deliberately still points to that fixed directory,
so it cannot silently consume another paid attempt. A later owner-directed
execution must first reconcile live account state and explicitly resolve the
consumed-attempt gate while preserving the original record; this CPU-only
request does not grant that next create. No new approval is requested here.

At actual execution time, refresh the authenticated stock/price/balance offer
and validate the prepared material again. Successful create/readback, public
port routing, pinned-image runtime behavior, internet transfer of the 23GB
model, hardware/driver/MIG checks, inference, one task, deletion and final billing
remain unobserved for A100. No extra paid diagnostic is proposed. The PR remains
Draft, Issue #1 open, and no merge, training or competition submission occurs.
