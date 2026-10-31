# CUDA comparison: initialization isolated, kernels still unqualified

The one authorized A40 comparison ran. It supplies evidence that the added
worker filter interferes with CUDA initialization, but no denied-syscall trace
or supported filter correction. No kernel, pretrained response, training step
or Augnes replay completed. Do not repeat this unmodified paid route.

The original failed run and all raw receipts remain unchanged in
[the evidence record](small-model-cuda-diagnostic-evidence-20261031.json).
The follow-up fixes two demonstrated collector/admission bugs using free tests;
it does not remove the filter or claim that CUDA is fixed.

## Observed comparison

Paid [run 41177113950](https://github.com/hynk-studio/backtrace/actions/runs/41177113950)
used source `7082d5d0756ba627eeff73ed467f0a3d29c4fe7b`, tree
`eae70a61d4ec94bc19c4473a22c591b72509d8e6`, one NVIDIA A40 in CA-MTL-1,
driver 595.91.07 and the pinned Python 3.12.14 / Torch 2.13.0+cu126 closure.
Provider readiness arrived at 171 seconds. Authenticated binary delivery,
3,642,438,227 runtime bytes, exact offline installation and device inventory
completed. Each comparison process exited and the GPU was idle afterward.

| Case | Boundary | Primary result | Supplemental result after primary |
| --- | --- | --- | --- |
| A | Provider container, root; no added worker filter | Availability/device-count/properties path completed; joint identity/memory/BF16 gate rejected before kernels | cuInit 0; cudaGetDeviceCount 0; one device |
| B | UID/GID 65532, no capabilities, no-new-privileges; no added filter | Same joint gate rejected before kernels | cuInit 0; cudaGetDeviceCount 0; one device |
| C | Same B identity/limits/environment, plus existing worker filter | Primary cudaGetDeviceCount warning 304; availability rejected | cuInit 304; cudaGetDeviceCount 304 |

All three could open the selected device, nvidiactl and nvidia-uvm. Runtime,
driver-library hashes and shared environment/limits matched; filter counts
were 1/1/2. The B/C difference implicates the added filter in **initialization**.
The exact denied syscall remains unknown. Supplemental calls followed each
primary probe; they are not independent samples or replacement kernel passes.

The original classifier returned `COMMON_PROVIDER_RUNTIME_PATH_STOP` because
it reduced all three primary outcomes to FAIL. That historical label is
preserved, but the raw stages do not support a common initialization failure.
Future classification says `ALL_PRIMARY_PROBES_FAILED_CAUSE_UNRESOLVED_STOP`
for this coarse pattern. No historical result is relabelled as success.

## Demonstrated free corrections

1. `connected()` wrote its receipt exclusively before the scope wrapper tried
   to write the same path. The second write raised `FileExistsError`, making
   the owner job FAIL after all comparison data had been retained. The wrapper
   now leaves that receipt unchanged and writes a separate summary bound to
   its SHA-256. A regression uses the actual exclusive writer, reproducing all
   four old-source subcase errors before the correction.
2. The pinned PyTorch [CUuuid binding](https://github.com/pytorch/pytorch/blob/v2.13.0/torch/csrc/cuda/Module.cpp)
   uses its [bare UUID formatter](https://github.com/pytorch/pytorch/blob/v2.13.0/torch/csrc/utils.cpp).
   The existing check compared that directly with nvidia-smi's `GPU-` prefix.
   It now normalizes only this spelling and requires the same complete UUID.
   Mismatched, abbreviated, malformed and MIG identities remain rejected;
   architecture, memory, native BF16 and exposed-node checks remain mandatory.
   A CPU-authored regression reaches only a marked kernel boundary, not a GPU.
   The paid joint rejection did not retain individual properties, so this
   static defect does not establish that every other device gate would pass.

Focused free validation: **26 tests passed**, preflight and whitespace checks
passed. Corrected source `112039ef3c3bdbe01d3f65bcc6753a8016ee1726` (tree
`dfa93b54d101f2e0c241b6faef445b102e835790`) passed
[free run 41178604712](https://github.com/hynk-studio/backtrace/actions/runs/41178604712),
attempt 1: **679 native tests in 141.941 seconds, no failures/errors/skips**,
all **17 ordinary-container controls**, and separate-runner cleanup with two
absence reads each. Three archives / 38 members and all 67 source hashes were
verified. The eleven paid state blobs and the paid start/prior review refs
remain unchanged. The production filter is byte-for-byte unchanged. No replacement paid permit,
second allocation or broader model execution is part of these corrections.

## Cost, cleanup and preservation

Pod `kpppr9w0btuce6` was deleted. Owner and independent watcher each observed
absence twice; watcher reason is `OWNER_DONE`. Both paid jobs terminated.
Complete inventory at 2026-10-31 06:49:24 UTC contained zero Pods. Account read
at 06:49:15 showed USD 2.9060441339, zero hourly spend and autopay off.
The observed balance decrease is **USD 0.1037751241**, not final billing evidence.
The later free-run read at 06:57:25 UTC retained the same balance/zero spend;
complete inventory at 06:57:33 again contained zero Pods.
The original USD 1 / 3,000-second / USD 0.50-reserve contract was retained.

All 67 executed source hashes, two paid archives / 23 members and eleven state
blobs were verified. Final paid state commit:
`13e7f67fa672dace6f45e637b0393bd7053c38d9`. The paid source, start ref and consumed
authorization remain immutable. Prior free qualification at the same source
passed all **677 native tests and 17 ordinary-container controls**, with
independent cleanup; three free archives / 38 members were verified. Preserve
the earlier zero-job YAML failure and Work-environment test failures too.

## Remaining research decision

The next CUDA measurement would need a bounded way to identify the denied
operation while keeping the production filter intact. A supported narrow
remedy must precede another same-route capability run; current receipts do
not justify broad permission relaxation. Hardware qualification also still
needs actual BF16 kernels and active-context teardown.

The 18 prepared E2B assignments are nine views of **one development episode**
under B0/B1, not nine independent episodes. The provider pretrained connection
is still unimplemented. Augnes's local connector was unavailable during the
source audit. Existing P3.3/P3.4/P3.5 and P5.1 records include authored or
fictional cases, including multiple contrasts of one family; none is counted
as the requested three-to-five historical business replays. Actual time-cutoff
source packets, model outputs and additional-main-model comparisons remain
unperformed. No training or product-value conclusion follows from this work.
