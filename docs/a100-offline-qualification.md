# Offline Linux CPU qualification — 2026-10-16 UTC

The exact original README and complete Linux wheel closure are restored. Actual
offline installs and official CPU checks now pass on Kaggle and in the pinned
PyTorch image's user-space. This advances preparation for the existing conditional
A100 attempt; it does not complete the full A100 driver or provider gates.
The owner explicitly permits a CPU-qualified private offline bootstrap on this
pinned public base, so a private image/registry is optional, not a prerequisite.
See the subsequent [free-resource assessment](free-resource-assessment.md).
PR #7 remains Draft; no intermediate merge or repeat GPU approval is needed.

## Restored inputs and portable wheels

An archival GitHub copy of `HARNESS_README.md` has exactly **49,356 bytes** and
SHA256 `3d6e57a13234cb4e783ba24eaab486459af76e0923ea4c6607cd41cc8961bbbb`,
matching the unchanged original source manifest. Two mirrors returned Git blob
`1b068740db714b8766e8f9c880fd8f03a53de161`; acquisition provenance is in
[the evidence record](a100-offline-evidence.json). This recovers pinned bytes;
the mirror is not a new competition contract. All 16 required artifact records,
including the ten-file original starter, pass verification. Notebook v2, the
6,230-byte candidate and five-field task input retain their existing identities.
Original assets and wheels remain private.

The portable bundle contains **245 runtime wheels plus pip 25.0.1 for bootstrap**,
246 files totaling **5,373,559,590 bytes**. All 245 runtime package versions match
the preceding proposal inventory. The approved three substitutions remain the
only changes to the original 41-wheel selection; the other 38 are byte-identical.
[linux-supplemental.lock](linux-supplemental.lock) pins the other 204 packages with
one selected wheel hash per row. [linux-wheel-manifest.json](linux-wheel-manifest.json)
records filenames, versions, sizes and hashes, without redistributing wheel bytes.

The combined 245-row lock is SHA256
`0472483ff319a2ae7e5a34292a80a37f2d890f969ddfc8903bea640ed3c09c26`.
Both completed installs produced the same inventory SHA256
`7823c323fa2effcfe5172bc63c39f1162323fee8312ade2534c66888f33c894b`.
The source manifest and approved amendment JSON are unchanged.

## Installer and cleanup fixes

The pinned base's `/usr/bin/python3.12` is Python 3.12.3 and lacks `ensurepip`.
The installer now creates a `--without-pip` venv and bootstraps from the separately
verified pip 25.0.1 wheel. It checks that wheel before environment creation,
records `bootstrap.lock` and its identity, and rejects supplemental repinning of
pip. Full hash installation, the selected 41-wheel force-reinstall, `pip check`,
imports, no-overwrite and rollback remain enforced. There is no online resolution
during qualification: pip uses `--no-index --require-hashes`, and a Python audit
hook denies socket operations. This is not an OS network-namespace test.

```sh
python3 tools/linux_runtime.py .local/linux-wheels docs/linux-supplemental.lock .local/linux-runtime
```

An initial official lifecycle run had two cleanup errors because `/bin/ps` timed
out. Linux group inspection now reads `/proc/*/stat`, rejects a foreign PID
namespace, and handles spaces, closing parentheses and non-UTF-8 process names.
An observation error during the grace period still reaches KILL and reaping;
the final absence check fails closed if metadata remains unavailable. One live
fixture left by the initial failed run was explicitly killed before revalidation.
The original failures are retained, alongside the successful final runs.

## Observed checks

| Check | Result and boundary |
| --- | --- |
| Kaggle offline runtime, CPython 3.12.14 | PASS, 397.910 s; fresh venv, full hash install, force-reinstall, dependency/import checks |
| Exact base user-space, CPython 3.12.3 | PASS, 447.686 s, including pinned pip bootstrap; same final inventory |
| Official candidate and compiler | PASS in both environments; actual candidate, request-rejecting client, no sandbox/task execution |
| Official callable/schema binding | 6 PASS in both environments |
| Actual wrapper argv | PASS in both; injected T4/A100 capability, no server start |
| Final standard-library suite in Kaggle | **87 PASS, 0 skipped**, 21.442 s; authored CPU process payloads |
| Final official wrapper lifecycle in Kaggle | **10 PASS, 0 skipped**, 18.365 s; real adk-submission 0.2.11 lifecycle with CPU payloads |
| Fatal detection / owned groups | Official maximum 0.621567 s; authored maximum 0.053790 s; final cases report zero owned processes remaining |
| Retained private-driver isolation phase | PASS with only scratch relocation; UID 65534/capability drop, unreadable root canary and parent environment, real sandbox dependency inheritance |
| Separate task overlay | Fixed Starlette 0.48.0 and pdm-backend 2.4.9; parent runtime still passes `pip check`; task scratch removed, zero owned descendants |
| Cloud full suite / preflight | 87 run, 12 errors from foreign procfs PID namespace; retained as failures. Preflight reports local tooling READY |

The base is the approved digest
`pytorch/pytorch:2.10.0-cuda12.8-cudnn9-runtime@sha256:b85566342b86d13a67712e9315d40cdc2dad7f8d86df1aff3831f80835edbcca`.
All six layer digests match; original and OCI-converted config JSON are
semantically identical despite serialization hashes differing. The image was
unpacked and executed with chroot and standard `/dev` character nodes on Kaggle's
host kernel. Mount/network namespace creation was denied. **Container isolation,
actual GPU/driver behavior and a deployable private image are not qualified.**

The complete private working output was downloaded as a ZIP with 434 members,
**5,380,090,470 bytes**, SHA256
`ad3e1a342f7527beade9ed75f25ec65692002f28d10efe3520af1a7961983ed3`.
The downloaded bytes match the Kaggle archive. This contains the wheels, locks,
tested sources, restored inputs and raw logs; it is not a deployable image.

**A new Kaggle saved version was not created.** The editor reports that the
notebook source exceeds its 1 MB limit. The GUI save did not advance version 3;
the CLI archive save returned HTTP 400. Automatic approval review rejected an
SDK retry because it could duplicate a version/upload. No further save request
was made. The full ZIP's separate durable upload also failed; it remains a local
verified backup, so durable wheel storage is still open. A smaller private ZIP
with source and evidence, excluding all wheel bytes, was saved successfully.
The public record contains metadata and hashes, not the private assets.

Temporary image layers, runtime environments and caches were removed, recovering
42,098,044,928 bytes; the cleanup readback found no live owned fixtures.
The Kaggle CPU session was then stopped; the UI reads `off (run a cell to start)`.

## Remaining prerequisites

Use the qualified offline bootstrap and complete A100 task/controller integration,
including provider-relative deadlines, one-attempt ownership and independent
deletion/readback. The owner has since clarified that no RunPod account exists;
this is not a missing existing login. Account creation/terms and any funding are
owner decisions before an authenticated offer, stock, balance, tax and
provider-native stop/delete acceptance can be checked.
Then qualify actual hardware and isolation before the authorized single start.
The existing EU-RO-1/full A100 80GB PCIe/TP1, $2 all-in and 3,000-second conditions
remain unchanged; no fallback, deposit or additional attempt is authorized.

GPU allocation, model download/load, serving, task generation, billing start,
submission and hosted scoring were **NOT RUN**. There is no task patch. No RunPod
resource was created, so provider deletion is NOT RUN, rather than a claimed
successful deletion. No merge, auto-merge or Issue #1 closure was performed.
