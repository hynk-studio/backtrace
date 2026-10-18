# Free preparation and rental assessment — 2026-10-16 UTC

**2026-10-18 amendment:** [Current prepaid preparation](a100-prepayment-ready.md)
and its [policy](a100-prepaid-policy.json) supersede the native-timer/$2 control
requirements below. Original observations remain historical evidence.

**Subsequent checkpoint (2026-10-17):** the owner has now created and signed into
RunPod. See the [prepayment audit](a100-prepayment-audit.md) for the current
account/resource boundary, updated price and native-timer failure evidence.
The account and quote statements below describe this earlier assessment.

The current frozen GPU experiment needs a suitable GPU beyond the resources
available in this Kaggle account. One bounded A100 80GB PCIe inference/task smoke
is justified once the remaining delivery and provider controls are ready. It is
not a training job, an instruction to fund RunPod, or a claim that A100 fit is
already proven. No paid resource was created.

## Observed free-resource boundary

The authenticated Kaggle editor's Accelerator menu offered **None, GPU T4 x2,
and TPU v5e-8**. None was selected; only a free CPU session was used. There was
no A100 option. The CLI's larger accelerator enumeration is not account access:
[official CLI documentation](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md)
explicitly limits some devices to particular competition participants or admins.
No hidden accelerator request, GPU allocation or extra T4 attempt was made.

The retained second T4 failure is a kernel **per-block shared-memory** limit:
98,304 bytes required, 65,536 available (96 KiB versus 64 KiB). It is not a
reported global-VRAM OOM. See [the original failure](r0-no-custom-ar.md).
Two T4s do not combine their per-block shared memory. Repeating the same frozen
configuration does not address that cause, and both T4 authorizations are spent.
TPU is not a drop-in device for the frozen CUDA/vLLM stack. A smaller model,
reduced context or changed kernel/runtime would be a different experiment.

[NVIDIA's Ampere guide](https://docs.nvidia.com/cuda/ampere-tuning-guide/)
documents A100's 163 KiB per-block capacity, above the historical 96 KiB request.
This supports testing A100; it does not prove TP1/native-BF16 kernel compilation,
model load, KV-cache capacity or end-to-end task success.

## Concrete CPU preparation

`python3 -m tools.a100_task <retained-private-driver> <new-private-directory>`
reproducibly prepares the private task driver. It verifies the original driver
hash before writing and refuses to overwrite an earlier output. The generated
source changes T4 checks/TP2/FP16 observations to the exact A100 gate/TP1/BF16,
uses the startup guard, and applies the approved setup/useful-work limits.

The original online setup/v25 reinstall block is replaced with a check of the
actual isolated CPython 3.12 runtime's complete 246-package inventory, including
pip. A nested task venv explicitly appends the qualified runtime's package path;
its fixed Starlette/pdm-backend overlay takes precedence without modifying the
serving environment. A real nested-venv test checks both inheritance and overlay
precedence. Foreign procfs PID namespaces are rejected before UID cleanup.

The transform asserts exact AST preservation of the organizer serving/evaluation
cells, environment, model/input pins, prompts/agent body and isolation functions.
The private source SHA256 is
`58880d27069574d10f60e90d3c80cbae89d080a4ed813206a973b49e6982ead2`.
Two preparations matched; overwrite and non-CPU entry attempts were rejected.

**The generated entry point currently permits only CPU prerequisites and the
isolated dependency check.** Provider/controller integration remains unqualified,
so this is not a deployable GPU launcher. `tests/official_a100_task.py` checks its
actual pre-start code with the real pinned wrapper and injected hardware, with
model start, subprocesses and network access denied during construction.

Execution results and exact hashes are recorded in
[free-resource-evidence.json](free-resource-evidence.json). Historical full-base,
compiler and binding successes are retained in the
[offline qualification](a100-offline-qualification.md), separately from new runs.

| New check | Observed result |
| --- | --- |
| Fresh Kaggle / CPython 3.12.14 suite | **90 PASS, 0 skipped**, 20.035 s |
| Fresh hash-pinned acquisition / offline install | 246 exact wheels; 92.228 s acquisition, 336.203 s installation; unchanged final inventory |
| Generated private driver's complete CPU mode | PASS, 14.611 s; original isolation and actual sandbox dependency inheritance, cleanup confirmed, scratch removed |
| Serving runtime after task overlay | `pip check` PASS |
| Actual official wrapper lifecycle | **10 PASS, 0 skipped**, 19.441 s; CPU payloads, no model |
| Actual private driver + actual official wrapper construction | PASS, 12.456 s; TP1/BF16/32k/guard argv; hardware injected, no server start or execution attempts |
| Original artifacts | 16 records and 10 starter files verified |
| Cloud full suite / preflight | 90 run, 12 foreign-procfs errors retained; preflight locally READY |

The first construction test wrongly expected the observer field before `start()`.
That test failure is retained. The corrected test checks the actual guard subclass
and command and requires the observation field to be absent, with startup still
blocked. A scratch control-script syntax error occurred before checks executed;
it and the corrected successful run are also retained. No production guard or
experiment pin was relaxed. Final authored/official lifecycle cases report zero
owned processes. Temporary runtime, wheels and caches were removed, and the CPU
session's `off (run a cell to start)` state was observed.

The first fresh download correctly stopped on a hash mismatch: PyPI returned
`safetensors-0.8.0-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`
with SHA256 `fd6f3f93c9a0a7cc2788ee63fb763353d4bd2e89b0751bc78fcf7dda00bea774`,
whereas the frozen Kaggle wheel is
`f216afd4ba743e744c86cbd08e7185efa8749e4c905f14e4e977d65576466cb0`.
The same filename/version is not a byte identity. The corrected private
acquisition recipe uses explicit local paths for all 38 unchanged Kaggle wheels,
with the approved three substitutions and supplemental hashes unchanged. It does
not accept the alternate bytes or amend a pin.

## Delivery and cost decision

The active [Issue #1 authorization](https://github.com/hynk-studio/backtrace/issues/1#issuecomment-5895260495)
allows **a CPU-qualified private offline bootstrap on the pinned public base**.
A private image, registry and extra image builder are optional. Earlier text that
made a private image mandatory overstated the prerequisite and is corrected.
Actual provider isolation/hardware and transport still need checks.

The owner has no RunPod account. Account creation/terms and wallet funding are
owner decisions; this is not a request to log into a nonexistent existing account.
The existing approval covers one conditional Secure Cloud EU-RO-1 full A100 80GB
PCIe/TP1 attempt, at most 3,000 seconds and $2 all-in consumption. It does not
cover account funding, automatic top-up, a paid builder or additional runs.

The public $1.59/hour reference models approximately $1.34 before tax for the
50-minute maximum and 100GB temporary container disk. This is not an authenticated
live offer. [RunPod billing](https://docs.runpod.io/accounts-billing/billing)
advertises starting with $10 of non-refundable credits; the actual checkout
amount/tax is unverified. Initial cash outlay is separate from the $2 experiment
consumption cap. No signup, terms acceptance, deposit or payment was performed.

Before renting, finish private delivery/readback and the independent controller,
then verify the exact authenticated offer/stock/tax and provider-native stop/delete
persistence. No credential belongs on the agent Pod. The controller must preserve
one-attempt ownership, handle ambiguous creation without another create, and
independently delete/read back the exact Pod. Until those conditions are met,
keep GPU entry blocked. The existing conditional approval need not be repeated.

## Private storage boundary

The full 5,380,090,470-byte ZIP remains locally SHA256-verified. A single bounded
alternative divided it into twelve parts with a manifest and safe no-overwrite
restore script. The prepared upload batch timed out; targeted search and a
newest-first file listing found no created parts. There is no claimed durable
wheel backup. Derived part copies were removed; the original full ZIP remains.

A compact private continuation notebook of **867,760 bytes**, below the 1 MB source limit, was prepared
and its compressed source round trip and syntax checked. It has not been pushed
or saved as a Kaggle version. The earlier automatic approval rejection of the
SDK save retry remains respected; no save retry was made through another route.
The new private evidence package excludes wheels and retains this notebook,
tested private driver, source hashes and logs. Its durable save succeeded:
968,501 bytes, SHA256
`4b8d7ee27457ba219c84adf9037331a4b7f4b9eacee9e2143fb542fde05eed05`.
Only authored tooling and metadata are committed publicly.

GPU allocation, model v2 download/load, serving, task generation, patch creation,
public verification, submission and scoring are NOT RUN. No new attempt marker,
billing start, merge, auto-merge or Issue #1 closure occurred. There was no Pod to
delete; provider deletion is NOT RUN, not a successful deletion claim.
