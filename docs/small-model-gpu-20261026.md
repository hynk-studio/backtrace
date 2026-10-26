# CUDA runtime verification and pretrained baseline preparation

Date: 2026-10-26. Refs [BT-001](https://github.com/hynk-studio/backtrace/issues/1).
Base: Draft #33, `aeb06af108a348c32422954c172b634c0bd5959e`.

The owner requested GPU environment verification and preparation for actual
E2B/E4B baseline measurement. This stage installs the already pinned CUDA
package set on free native CPU, extends the isolated collector for explicit
CUDA execution and resource measurements, and prepares the unchanged smoke
assignment. There is no GPU in the current Work environment. Package imports,
CPU tensors and a character-device control do not establish an actual NVIDIA
driver/kernel/device result. No paid allocation, pretrained inference or training
is performed in this preparation.

## What is implemented

`tools/small_model_gpu.py` verifies all 56 exact CUDA wheels against the existing
lock, checks the installed package set without extras, and imports the CUDA build
and its dependencies. It checks native shared-library resolution and records
the actual library hashes. PyTorch remains 2.13.0+cu126, compiled against CUDA
12.6, with Python 3.12.14 and Transformers 5.20.2. The old lock and requirements
remain unchanged; their historical RESOLVED status is not rewritten as evidence
that installation had happened previously.

The actual-device entry requires a full GPU UUID, a supported NVIDIA driver,
one non-MIG GPU with at least 24 GiB reported memory, no existing compute/graphics
processes, and the fixed worker UID's access to the selected device nodes. It
uses the reported **minor number**, not the enumeration index, to select
`/dev/nvidiaN`. It mounts that node, `nvidiactl` and `nvidia-uvm`; no whole `/dev`
or host `/sys` mount is added. CUDA_VISIBLE_DEVICES names the same UUID but is
not treated as the isolation mechanism. Selected host driver libraries are
hashed, copied to disposable staging and mounted read-only. Driver cache writes
are disabled. Private network/PID/user namespaces and input-only mounts remain.

`probe-device` first repeats filesystem/network/privilege and detached-child
deadline/parent-loss checks with the proposed device mounts. The isolated CUDA
worker then requires the expected UUID, exactly one CUDA device, native BF16,
compute capability at least 8, and the memory floor. It executes small BF16
matrix multiplication and SDPA controls and synchronizes the device before
reporting success. Missing CUDA, driver mismatch or unsupported devices fail;
there is no CPU fallback. These positive GPU checks are implemented but NOT RUN
on physical hardware here. A GPU-context-bearing process killed mid-kernel and
driver fault recovery still require hardware qualification; the existing
detached-child boundary checks do not establish those properties.

`run-existing` is an explicit command for an already provisioned native Linux
host. It does not download model weights or allocate/delete hardware. It checks
host RAM and room for disposable weight copies, runs the device probe, and
performs 36 tiny random CUDA diagnostic requests before attempting full
checkpoint verification/loading. The diagnostics have at most two new tokens
each and are reported separately from the 36 pretrained baseline requests.
All diagnostic work counts within the proposed allocation budget.

Full local checkpoint sizes and SHA-256 hashes are required. The unchanged
official header/layout inspection and explicit full-wrapper/text-model mapping
precede loading. The worker uses BF16 and SDPA with all model parameters on
cuda:0, no quantization or CPU/disk offload, and rejects missing or mismatched
text weights. It reports synchronized response wall time, load time, and peak
allocated/reserved GPU bytes. These allocator measures are not total device
usage: the report also retains CUDA free/total memory, and a real hardware run
still needs external memory observation for driver/context and other overhead.
No first-token latency or steady-state benchmark is claimed by the current
whole-response timing.

## Fixed measurement scope and resource proposal

The [prepared plan](small-model-gpu-baseline-v1.json) is generated from the same
source-bound smoke, tokenization report and original input bytes. It fixes E2B
then E4B, with B0/B1 interleaved within each model. All 36 assignments cover just
one development family/episode and nine views; they are not 36 independent
samples or confirmatory evidence. The four packet grids still have 11,520 actual
tokenization assignments with no overflow. Screening and controlled-English
execution remain separate later work.

Greedy, no-thinking, batch one, no tools, 12,288 input / 4,096 new-token ceilings
and original raw-token treatment are unchanged. A timeout, crash or malformed
response preserves the received evidence and unexecuted remainder. There are no
replacement cases or retries. Assigned-denominator protocol penalties remain
separate from scores conditional on received responses.

| Item | Prepared requirement or proposal |
| --- | --- |
| GPU | One exclusive non-MIG device; at least 24 GiB reported memory; native BF16 |
| Driver | At least 560.35.05, a conservative CUDA 12.6 baseline; actual kernels still required |
| Host | At least 32 GiB RAM; 64 GiB free disk after runtime installation, before both checkpoints |
| Full checkpoint bytes | E2B 10,246,621,918; E4B 15,992,595,884 |
| Sources plus disposable copies | 52,478,435,604 bytes, excluding runtime, tokenizer, logs and reserve |
| Total proposed allocation window | 3,000 seconds including setup, diagnostics and deletion |
| Planning split | Setup/diagnostics target 900 s; collector at most 1,800 s; cleanup reserve 300 s |
| Individual collector limits | Model startup 180 s; request 90 s; no retry |
| Existing conditional cost ceiling | USD 0.90 compute + USD 0.10 other; USD 1.00 total, with USD 0.50 balance reserve |

These are limits, not a price quote or a prediction of completion. The full
weights total about 26.24 GB; transfer, hashing, installation, model loading and
worst-case decoding may not fit the window. The global collector deadline can
produce partial coverage, which must stay visible. E4B's previously measured
meta-parameter BF16 storage floor already exceeds the owner's 12 GiB deployment
target. Quantization and Augnes deployment are separate experiments.

The local command's collector clock starts after asset staging. It is **not an
allocation-inclusive controller**. A fresh provider lifecycle connection must
enforce the outer deadline, export evidence and independently prove deletion
before any paid use. Existing consumed permits/controllers/watchers are not
reused. Current stock, quote and balance have not been fetched in this step;
no paid permit is created by the prepared plan.

## Reproduction and qualification

The [native workflow](../.github/workflows/small-model-gpu-cpu.yml) uses free
Ubuntu CPU, runs the full test suite and the complete previous CPU collector
controls against the changed source, then downloads all CUDA wheels with their
frozen hashes and installs into a separate fresh traversable venv offline.
`pip check`, package identity, native linkage and CPU compatibility are checked.
The CUDA build then exercises both tiny random model paths and authored exact
controls on CPU, plus an actual isolated worker rejection when no GPU is present.

A separately created character device with major/minor 1:3 exercises the actual
bind and unprivileged write path. Namespace boundary and process-death controls
repeat with this extra device mount. This is expressly a character-device
mechanism check, not an NVIDIA ioctl, GPU context, kernel or memory result.

Commands for preparation on CPU:

```sh
python -m tools.small_model_gpu verify-wheels .local/cuda-wheels
"$BACKTRACE_CUDA_RUNTIME/bin/python" -m tools.small_model_gpu check-runtime
python -m tools.small_model_gpu prepare .local/smoke .local/packets .local/tokenization.json .local/gpu-baseline-plan.json
```

Actual-device commands are for a later authorized existing resource only:

```sh
sudo "$BACKTRACE_CUDA_RUNTIME/bin/python" -m tools.small_model_gpu probe-device GPU-REPLACE-WITH-FULL-UUID .local/device-probe
sudo "$BACKTRACE_CUDA_RUNTIME/bin/python" -m tools.small_model_gpu run-existing GPU-REPLACE-WITH-FULL-UUID .local/model-sources .local/full-checkpoints .local/smoke .local/packets .local/tokenization.json .local/pretrained-smoke
```

Use fresh output directories. A native Linux root coordinator with namespace
capabilities is required. The Work container is not a substitute for that
environment. Initial local focused tests passed 29 checks; a later GPU-contract
focused run passed all 12 checks. The local full suite attempted 604 tests in
150.379 seconds and failed with 5 failures, 10 errors and 4 skips in the existing
pip-fixture/startup/procfs checks. This remains a failed local observation.
Exact-source native qualification below is a separate observation. No positive
hardware check is inferred from free CPU qualification.

Final native [run 40335270281](https://github.com/hynk-studio/backtrace/actions/runs/40335270281)
at `2ea31a8b5f17684a6c82f2452cf3072d42f8329a` succeeded on its first attempt:

| Observed check | Result |
| --- | --- |
| Full native suite | 604 tests in 179.361 s; zero failures/errors/skips |
| Existing CPU collector path | All ten original pipeline checks and namespace controls passed |
| CUDA wheel bytes | All 56 verified; total 3,606,157,908 bytes |
| Fresh offline CUDA install | Exact installed package set, pip check, imports and native linkage passed |
| Actual hardware availability | Zero CUDA devices; no physical GPU execution |
| Missing-GPU worker | Failed with the exact no-CPU-fallback error before model execution |
| Real character-device control | Explicit 1:3 bind and unprivileged write passed; NVIDIA ioctls NOT RUN |
| CUDA-build authored control on CPU | 36 valid responses; all per-case and paired losses zero |
| CUDA-build random generation on CPU | 36 responses retained as INVALID_OUTPUT under the two-token limit |
| CPU/CUDA-build comparison | Tiny checkpoint bytes and all 36 CPU raw outputs identical |
| Prepared baseline | Native generated bytes match the committed original-smoke plan |

The [verification receipt](small-model-gpu-cpu-20261026.json) records the source
commit/tree, 21 source hashes, actual wheel/library bytes, run and artifact.
ZIP SHA-256 is `35a118e997dba01591be43f74f11896b7bf500ac589ddea4d888eba1094ac442`.
All 109 archive members were independently hashed; 50 CPU and 24 CUDA-build
exported scenario files matched their inner receipts. The original 13
scientific/runtime hashes and five preparation artifacts remain unchanged.
The final focused local suite passed 29 checks in 27.793 seconds; its earlier
full-suite failure remains a distinct failed result.

This qualifies installation and CPU behavior of the CUDA build. Hardware
compatibility, cgroup/container memory headroom, full-size resource feasibility,
GPU-context interruption and the outer provider lifecycle remain unqualified.
The positive actual-GPU branches of the new worker were not exercised here.

## Primary sources and remaining evidence

Read 2026-10-26 UTC:

- [CUDA 12.6 Update 3 release notes](https://docs.nvidia.com/cuda/archive/12.6.3/cuda-toolkit-release-notes/index.html)
  identify toolkit component versions and driver 560.35.05. The selected driver
  policy is deliberately stricter than the limited CUDA 12.x compatibility floor.
- [NVIDIA minor-version compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html)
  documents feature/PTX limitations; version numbers alone cannot qualify kernels.
- [NVIDIA device and driver exposure](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html)
  distinguishes device enumeration from compute/utility driver libraries.
- [Bubblewrap mount/namespace reference](https://github.com/containers/bubblewrap/blob/main/bwrap.xml)
  supplies the mount option semantics. Actual mechanism evidence comes from the
  native controls, not the documentation.
- The installed pinned PyTorch 2.13 CPU source was inspected for CUDA device,
  native-BF16, synchronization and peak-memory APIs. The versioned web CUDA API
  page could not be retrieved; it is not cited as an inspected source.

A1 remains partial. Physical NVIDIA device/driver validation, pretrained
performance, realistic transfer, power analysis and final sealing remain open.
A2 update/save-reload, training, quantization, Augnes adoption and Kaggle
submission are NOT RUN. The next paid decision requires a concrete current
resource/price/balance proposal and qualified outer lifecycle, not simply a
successful CUDA package install.
