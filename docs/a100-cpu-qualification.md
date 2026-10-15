# A100 follow-up: CPU implementation, allocation not attempted

This is the original Cloud report. The later
[Kaggle CPU follow-up](kaggle-cpu-followup.md) records successful authenticated
access, exact driver/notebook restoration, official lifecycle execution, and
three dependency conflicts. Its tested replacement proposal is separate from
the unchanged frozen runtime. The historical observations below are preserved.

Recorded 2026-10-15 UTC (2026-10-16 Asia/Seoul), from main
`23616971a4ec57d32fcce769e0a2abf44faa9cfe`, tree
`0c6c3ca4b17d1ac954e3e805363c773fe513f4f7`, on
`bt-001-a100-cpu-qualification`. Main was fetched/rechecked; PR #6 is merged,
Issue #1 is open and no other open PR was returned before this work.

The [owner's authorization](https://github.com/hynk-studio/backtrace/issues/1#issuecomment-5895260495)
permits one conditional full A100 80GB PCIe/Secure Cloud/on-demand/EU-RO-1/TP1
attempt, all-in $2 and allocation-request-to-deletion <=3,000s. The 1,200s setup
and startup limits, useful-work cutoff 2,700s, provider stop 2,880s/terminate
3,000s, native expiry readback and independent owner-side deletion remain gates.
No wallet funding, fallback, retry, second allocation or submission is implied.

## Changes and evidence boundaries

- Positive-path CPU fixtures now have a 12s startup budget. A real subprocess
  regression delays parent boot by 4.2s, exceeding the former 4s budget. The
  post-evidence detection assertion remains <5s and the explicit 0.6s deadline
  tests remain. Production `tools/startup_guard.py` and its deadlines are unchanged.
- Linux lifecycle tests temporarily become a child subreaper and restore the
  previous setting. This deals separately with container PID 1 orphan reaping.
  Every lifecycle case asserts the owned process group and recorded descendant
  PIDs are gone; TERM/KILL fallback and idempotent cleanup are exercised.
- `tools/a100_driver.py` adds an A100-only serving constructor using the pinned
  notebook's actual config expression, the existing native-only BF16 transform,
  TP1 and no-custom-all-reduce. It rejects other GPU variants, MIG/unknown MIG,
  insufficient memory, old driver/toolkit, non-SM80, multiple visible devices,
  emulated BF16, adapters, and an exhausted setup clock before constructing the
  guarded wrapper. It does not allocate, start a model or run a task by itself.
  Hardware observations in the new unit tests are **injected**.
- `tools/linux_runtime.py` verifies all 41 v25 wheel bytes, combines them with an
  exact supplemental hash lock, and qualifies a fresh private CPython 3.12 Linux
  x86_64 venv. Installs use no-index/require-hashes/only-binary, then the 41-wheel
  no-deps/force-reinstall step, pip check, imports and inventory. Child processes
  clear credentials and reject Python network requests, including direct URLs.
  Failed qualification removes its new environment; existing output is refused.
  The real disposable venv/pip regression fails on an absent transitive dependency
  and confirms rollback. Synthetic wheels do **not** establish official closure.
- The opt-in actual-wrapper argv check now calls the new A100 constructor.
  Actual-wrapper lifecycle cases inherit the 12s allowance/subreaper fix and
  delayed-boot regression. These official integrations are **NOT RUN here**.

The retained 33,461-byte private T4 driver is absent in this Cloud checkout. Its
hash-only public transform cannot reconstruct it. The A100 serving seam is useful
preparation, **not a complete qualified task driver**: restoring and adapting the
private root/dropped-UID task/cleanup code, CPU-checking the actual wrapper and
verifying provider-host isolation/expiry remain necessary. No T4 assertions were
silently reused as A100 execution. BF16/TRITON_ATTN remain source expectations.

The PR #6 review's original **14/15 PASS, one four-second fixture timeout** and
its successful separate 12s diagnostic remain historical results. The published
Cloud environment's earlier 66-test pass also remains separate from this run.
The referenced `start_skill` was not exposed in the current skill catalog or
workspace; the test-owned Linux subreaper is now reproducible in the repository.

## Commands run in this Cloud environment

Linux x86_64, Python 3.12.14; private logs under ignored `work/`.

| Command | New result |
| --- | --- |
| `python3 -m unittest discover -s tests -v` | 80 PASS; real disposable CPU processes and offline pip failure/rollback |
| `python3 tools/backtrace.py preflight` | Local tooling READY; official stages NOT RUN |
| `python3 tools/backtrace.py verify-artifacts .local/official` | Exit 2, missing artifact directory; verification did not pass |
| `python3 tools/compile_probe.py .local/official .local/r0-clean/build-a.zip --official-python .local/cpu-checks/bin/python` | Exit 2, FileNotFoundError before official construction |
| `python3 tools/linux_runtime.py .local/linux-wheels .local/linux-supplemental.lock .local/linux-runtime` | Exit 2, missing input; no environment created |
| `python3 -m py_compile tests/official_server_command.py tests/official_startup_guard.py tools/a100_driver.py tools/linux_runtime.py` | PASS; syntax only |
| `git diff --check`, `git diff origin/main...HEAD --check` | PASS on delivered commit |

Actual candidate `official_check.py`, `official_startup_guard.py` and
`official_server_command.py`: **NOT RUN**, because the official wheels, candidate,
notebook and `.local/cpu-checks/bin/python` are absent. No mock or alternative
package is counted as their execution. Detailed current measurements and receipt
hashes are in [a100-cpu-evidence.json](a100-cpu-evidence.json).

Once restored, the offline qualification command takes the verified wheel
directory, complete Linux supplemental lock, and a **new** output directory:

```sh
python3 tools/linux_runtime.py .local/linux-wheels .local/linux-supplemental.lock .local/linux-runtime
```

This does not resolve/download latest dependencies or manufacture a missing lock.
Run it on the pinned base before allocation, followed by the existing official
candidate/compiler checks. Keep the task venv/Starlette 0.48.0 separate.

## Acquisition and provider checks: first blockers

The current enforced Cloud policy has no Kaggle or RunPod allowed destinations,
no TCP domain/IP grants, no VPN, no configured secrets/runtime variables/outbound
identities. Standard Kaggle/RunPod credential locations and relevant variable
presence checks found none; no secret values were read. Neither Kaggle nor
runpodctl CLI is installed. SSH is installed but there is no permitted private
transport or authenticated endpoint for a remote-command probe.

Small read-only requests to the competition file-list endpoint, exact wheelhouse
v25 listing and RunPod Pod list returned **proxy CONNECT 403 Forbidden**; no API
authentication, quote, balance, regional inventory or resource list was obtained.
The exact `adk-submission==0.2.11` PyPI metadata request returned 404; another
version was not substituted. No competition entry or terms were requested again.
The authoritative 41-wheel/eight-model-file manifests remain in
`docs/source-manifest.json`; no Kaggle bytes were restored and no model downloaded.
The historical macOS CPU lock is not a supplemental Linux runtime lock.

The managed Docker daemon (28.4.0) was reachable. The exact pinned public base
was **actually pulled**, including layers, and Docker returned digest
`sha256:b85566342b86d13a67712e9315d40cdc2dad7f8d86df1aff3831f80835edbcca`.
However, expansion exhausted the Cloud's 32GiB workspace filesystem; the next
sandbox command failed with `No space left on device`. No container, pip install
or import qualification on that base ran. Deleting **only this newly pulled
image** succeeded, its exact image/config and layers were reported deleted,
the subsequent Docker image list was empty, and `df` reported 30GiB available.
No storage-driver change, paid builder/registry or persistent volume was used.
Pull success is not image/runtime qualification.

## Frozen identities and unrun GPU stages

- Task `fastapi_11194`; model `google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2`.
- Candidate 6,230 bytes, SHA256
  `2e24495826cb971053439a00d9ad8350471fc0efffa41a54b82082feedaa7358`.
- Five-field input SHA256
  `6ed92f4e646c17728aa8b9ca433a032d61b6b06827eec463a02c00f331c25d60`.
- Neither artifact was rebuilt or newly rehashed here. Prompts, AgentTool,
  no-adapter/context32768/sampling/cache/compaction and 1min/10 tools/50 turns/
  60s-command budgets are unchanged. Reference/tests stay outside the agent Pod
  until every descendant has stopped; provider credentials stay owner-side.

Authenticated current quote/tax/balance/stock, native expiry persistence,
allocation, hardware qualification, weight load, health, returned model request,
task/tools, patch and public-test verification: **NOT RUN**. Zero allocation
requests, zero server starts, zero task executions, no new attempt marker, and
no experiment charges initiated. There is **no generated task patch**, distinct
from a generated empty patch. No RunPod resource exists from this task to delete;
provider deletion/billing readback is **NOT RUN**, not a successful cleanup claim.
Competition submission/hosted scoring/training/merge/issue closure: NOT RUN.

One owner action remains: update this Cloud environment's secure configuration
with existing Kaggle and RunPod access, permitted Kaggle/API/download and RunPod
API/SSH transport, and enough free CPU scratch capacity for the pinned base and
private staging. No credentials in chat, manual artifact preparation, wallet
top-up or repeated GPU approval is requested. Resume the same authorized attempt
only after restoration, full Linux/driver qualification and live provider gates.
