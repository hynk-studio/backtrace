# First funded A100 create attempt — 2026-10-19

**GPU execution did not start. The create request failed, and the current transport is not deployable.** The owner funded USD 10 and instructed the approved one-attempt run. One create request was sent at **16:18:29 KST**. No Pod ID was received; repeated complete authenticated Pod lists contained zero Pods. The observed balance remained USD 10 and spend rate USD 0.000/hour.

## What happened

The unchanged qualified source (`9b08f11a3e59`, 39 source files) and all **280 inputs / 28,893,831,958 bytes** passed their SHA-256 checks before the request. The offer was Secure EU-RO-1, one A100 PCIe 80GB, fixed PyTorch digest, 100GB temporary disk, no persistent volume, USD 1.79/hour compute plus USD 0.014/hour disk. The paid receipt showed USD 10 paid for USD 10 credits, without an extra line-item charge. No additional fee appeared in the authenticated hourly quote; these observations were used in the offer and are not a general tax ruling.

The inline SSH initializer made the serialized create body **863,192 bytes**. RunPod's [official v2 OpenAPI](https://api.runpod.io/v2/openapi.json) limits it to **102,400 bytes** and documents rejection before authentication/processing. This constraint was present in the previously acquired specification and was missed in preparation. CPU transport tests did not validate the provider's complete wire-body limit.

The original journal retained only `ProviderError`, not its HTTP status. Therefore the size defect is verified, but **HTTP 413 was not preserved as a directly observed response**. Do not replace that distinction with a claim that stock alone caused the failure. Stock changed between checks and was LOW again at 16:21 KST.

## Resource and cost reconciliation

- Complete authenticated Pod lists at 16:19:56 and 16:21:14 KST were empty; an additional read at observer closure also found no Pods.
- Final check at **16:32:20 KST**: complete Pod list still empty, billing API records/total zero, controller not running and temporary key file absent. The refreshed account UI still showed USD 10.00 and USD 0.000/hour.
- The free controller was stopped at 16:22:54 KST after those checks. Its temporary API key file was removed; the original consumed journal was preserved.
- **One create request, zero confirmed allocations, zero server starts, zero tasks.** No second create, alternative GPU or region was attempted.
- This is **no resource observed after failed creation**, not successful deletion of an identified Pod. The original `cleanup_unresolved` journal was not rewritten to claim deletion.
- Account UI: USD 10 balance / USD 0.000/hour / Auto-Pay Disabled. Billing API: zero records and total amount zero. The provider says billing data can lag by one hour; this is current observed spending, not a finalized invoice.

## Correction and verification

The controller now checks the **exact JSON wire bytes** before preparation can succeed, before the paid entry loads a provider key, before an attempt journal is created, and before HTTP transmission. Oversized bodies fail locally without consuming a new attempt. Provider errors retain their numeric HTTP status while excluding response bodies, URLs and credentials.

Four regression tests cover an oversized real-sized initializer, no network/journal side effects, the exact inclusive byte boundary and escaped Unicode, preparation/paid-entry rejection, and safe HTTP status recording. The actual 863,192-byte initializer was also tested and is now **BLOCKED BEFORE API**.

| Environment | Result |
| --- | --- |
| Kaggle retained CPython 3.12.14 | **154/154 PASS**, no skips; 31.250 s unittest time; CPU preflight READY |
| Cloud focused controller/job tests | **46/46 PASS**, 4.963 s |
| Cloud full suite | 142 pass / 12 existing foreign-procfs namespace errors; 18.629 s; preflight READY |
| Initial Kaggle kernel CPython 3.13.15 | 150 pass / 1 missing-ensurepip error / 3 skips; preserved, then rerun with the qualified interpreter |

The notebook kernel had changed to Python 3.13.15 despite the saved environment selection. The retained Python 3.12.14 executable's permission was restored after Files-only persistence and used for final qualification. No runtime dependency pin, frozen driver, model, prompt, candidate or task changed.

## Remaining blocker

**The size guard is fixed; the SSH delivery design is not.** The existing inline binary cannot fit the API body limit. It must be replaced with a qualified transport and the actual complete create request must pass the new gate before another deployment proposal. No second paid request is authorized by this consumed one-attempt record. The source remains on Draft PR #7; Issue #1 stays open. No training, submission or merge occurred.

Machine-readable evidence: [a100-first-create-evidence.json](a100-first-create-evidence.json). Private logs, raw journals, keys, model files and task assets are excluded from Git.

