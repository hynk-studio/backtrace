# Minimum diagnostic and full execution comparison

Scope: the owner's instruction to proceed with the free difference audit after
the successful minimum diagnostic. Base: bootstrap-probe review commit
`e655960cb7db584e869709ba3c504dedcd73dee0`, stacked on Draft PR #12. This work
does not create another authorization, allocation or launch branch. References #1.

## What the actual diagnostic establishes

Run [39743403014](https://github.com/hynk-studio/backtrace/actions/runs/39743403014)
at `f7cb1164e06586486254ce193e30201e12e5c424` observed a valid CA-MTL-3 endpoint
after 101 seconds, mutual TLS, pinned SSH, and A100 81920 MiB through nvidia-smi.
Worker exit was zero. Both controllers confirmed absence. This observation did
not execute torch/CUDA kernels, install the full runtime, load the model or run
the public task. The older US-KS-2 timeout remains unexplained.

## Differences and their consequences

| Boundary | Minimum diagnostic | Full execution | Assessment |
| --- | --- | --- | --- |
| Provider request | Pinned PyTorch image, 1 A100, 100 GB temporary disk, port 22, custom initializer | Same make_request and transport profile | Equal for the same region/ephemeral identity; no provider create needed to compare |
| Region | CA-MTL-3 observed success | Earlier failed attempt used US-KS-2 | Region differs; one success cannot identify the earlier cause |
| Controller | cloud_owner with a separately scoped 1200/1500/1800-second envelope | Same controller with 1200/5400/6900/7200-second boot/setup/useful/total limits | Diagnostic success is shorter and has a different worker; all limits include allocation time |
| TLS transfer | Fixed verified executable | Same executable and deliver function | Actual diagnostic evidence applies to this shared mechanism |
| Initial SSH | Per-process timeout 25 seconds, nominal wait 60 seconds | Old remote(['true']) could use all remaining setup time in one subprocess | Corrected to one shared helper with a real cumulative deadline |
| Driver transfer and remote envelopes | Not exercised | Manifested SSH transfer, code/hash over stdin, private HTTPS source envelope | New free exact-image boundary check uses fixtures and a public pinned pip wheel; scientific streams are not qualified by fixtures |
| System packages | Not installed | Hash-pinned git/patch dependencies | New check executes this exact code through SSH in the deployment image |
| Runtime and GPU execution | nvidia-smi only | Full Python closure, torch device check, weights, activation, vLLM, agent and retrieval | Full runtime was qualified historically on CPU; changed complete source must be requalified before any later paid proposal |
| Scientific task and evaluation | None | Frozen Gemma checkpoint/harness/public task | NOT RUN by this audit; authored/fixture outputs are not model scores |

## Corrections

`ssh_bootstrap.wait_for_command` now bounds each initial SSH subprocess to the
smaller of 25 seconds and the remaining shared 60-second budget. Only exit 255
without identity/authentication failure may repeat. Remote nonzero exits, key
failures and expired deadlines fail immediately. Both the diagnostic and full
worker call this helper. A regression actually starts and terminates a hung
child; other controls cover transient recovery, late success and terminal errors.

`cloud_worker.setup_remote` now records FAIL with its specific setup stage,
error type and optional return code before propagating the original exception.
Commands, scoped URLs and stderr do not enter these projected events. The
encrypted private log remains the place for detailed inspection.

The separate free workflow has contents:read, no account secrets and no provider
client calls. Its real container uses the unchanged initializer, fixed transport,
pinned SSH, actual manifest receiver, actual code_envelope/direct_envelope,
base UID/disk check and pinned system-package installation. It downloads only
public pip wheel fixtures for the HTTPS stream check. Full runtime installation,
model transfer, launch permit and public-task execution are absent.

## Evidence and interpretation

Final source `54a42e05c6c0b0b890ad7ef2a7c061e2c304c5ea` passed actual free run
[39772757946](https://github.com/hynk-studio/backtrace/actions/runs/39772757946),
job 119805963874, attempt 1. The exact public report is retained byte-for-byte in
`full-path-parity-result-20261022.json` (3539 bytes, SHA-256
`8a1818017e446bd4849bc398740b3ff05cfd42c526c9d06be54257718981f3cc`).
It records nine passing checks, including the actual production setup prefix:
base_environment, system_packages, runtime_inputs; it stops before runtime
installation. The 81200-byte source envelope used a 422-byte command; a changed
source was rejected. Manifested SSH transfer verified 176128 fixture bytes.
All 24 pinned system packages installed and the dropped-UID git/patch smoke
passed. Two public pip-wheel fixture streams transferred 3683052 bytes with
verified hashes. No scientific task/model bytes were transferred.

Exact-source Linux run 39772757948/job 119804106450 passed all 324 tests and the
actual minimal HTTP regression. The local full suite ran 324 tests with the same
known foreign-procfs 5 failures, 7 errors and 2 skips; local preflight passed.
A status-write failure regression also verifies that retention cannot replace
the original remote exception. Four encrypted private logs were recovered and
verified (291170 plaintext bytes); bootstrap key files and private source maps are not collected.

Two earlier free workflow revisions passed their actual checks but failed
artifact export because the root-created evidence directory was not traversable
by the upload action. The final workflow grants traversal only to the projected
report/ciphertext directory. Final export succeeded; earlier private ciphertext
was not retained. Execution and source details are in
`full-path-parity-execution-20261022.json`. All 18 allocated start/watch refs and
the state-branch head remained unchanged.

The original full receipt binds 75 files and predates bootstrap changes. The
current full qualification closure has 80 files. The old receipt is intentionally
preserved and rejected for changed source; the minimum diagnostic receipt cannot
replace it. This free boundary workflow is additional evidence, not a complete
full-execution qualification receipt. A later full run still requires renewed
complete-source qualification and its own owner authorization.

Meta-assessment: the timeout correction prevents one initial SSH hang from using
most of the paid setup window. Stage failure records improve diagnosis rather
than preventing the underlying failure. The boundary check can expose transfer,
quoting, command-size, UID and network-input errors on free CPU. None of these
checks predicts model correctness or guarantees a future provider allocation.
