# A100 prepayment audit — 2026-10-17 UTC

**2026-10-18 amendment:** [Current prepaid preparation](a100-prepayment-ready.md)
and its [policy](a100-prepaid-policy.json) supersede the native-timer/$2 control
requirements below. Original observations remain historical evidence.

**Decision: hold payment and allocation.** Sign-in is resolved, but the approved
provider-native stop/delete control is not established. Existing CPU results
remain useful; this is not a ready-to-run GPU system. No new allocation attempt,
funding, credential, SSH registration, payment-method change or terms acceptance
was performed. The owner created the account and completed Google sign-in.

This checkpoint corrects an important earlier assumption: GraphQL accepting
expiry input fields is not evidence that RunPod schedules or enforces them.
The new evidence below makes that problem concrete. It is not merely a missing
login or API key. The approval in
[Issue #1](https://github.com/hynk-studio/backtrace/issues/1#issuecomment-5895260495)
still requires both native expiry and an independent owner controller. It does
not authorize silently replacing native expiry with a notebook timer.

## Provider control evidence

| Evidence | Result and limit |
| --- | --- |
| Official runpodctl [PR #330](https://github.com/runpod/runpodctl/pull/330), merged 2026-08-27 as `51ca7f02ab5cb57c09ad917172af36c29a58790c` | Removed both timer flags after the provider observed accepted deadlines failing to stop running/billing Pods. This is upstream execution evidence, not our GPU test. |
| Official restoration [PR #331](https://github.com/runpod/runpodctl/pull/331), closed unmerged 2026-10-05 | Its body requires a backend enforcement fix first and explains that an echoed deadline proves only what the client sent. |
| Our unauthenticated production GraphQL read-only compatibility request, 2026-10-17 04:28:55 UTC | HTTP 400, `GRAPHQL_VALIDATION_FAILED`: both `stopAfter` and `terminateAfter` cannot be queried on `Pod`. No Pod ID or mutation was sent. |
| Earlier unauthenticated production schema inspection in this session | HTTP 400, `INTROSPECTION_DISABLED`. Authenticated introspection was not tested. |
| Public [REST v2 OpenAPI](https://api.runpod.io/v2/openapi.json), retrieved 04:33:20 UTC | HTTP 200; 274,963 bytes; SHA256 `fe8a74b177282ec89a9ba1c75d3ce1d4bd1a2a9b9609fbdb4bd131d5b4a24506`. Resolved Pod/create/update/action schemas expose no stop/delete deadline. |
| REST v1 account-list reachability, no credentials | HTTP 401. The executor reaches the endpoint; historical HTTP 403 is no longer the observed blocker. Authenticated list/delete/billing is still NOT RUN. |

The compatibility request was a single ordinary read query for the exact fields
used by the current adapter, with `input: null`; it did not enumerate resource
identifiers or retrieve account data. The v2 schema audit resolves references
and composition before checking properties. An initial shallow extraction
returned empty property lists for composed schemas; that extraction was corrected
before reaching the result recorded here.

[Evidence JSON](a100-prepayment-evidence.json) records the observations and
source identities. The published GraphQL spec and older Pulumi source still
carry create-input fields; they do not override upstream failure evidence or
establish a usable independent readback. No claim is made about an inaccessible
internal backend fix or every possible provider feature.

The current controller's authenticated schema gate should fail closed unless a
real supported contract is established. Its fake-provider test successes are
not RunPod integration successes. Do not remove that gate, send a paid test
allocation to discover the answer, or treat a local timer as native expiry.

The [official migration guide](https://docs.runpod.io/api-reference-v2/migrate-from-v1)
also schedules REST v1 retirement for **2026-11-15**. The existing controller uses
REST v1 for read/stop/delete. A later qualified integration must address v2's
changed response shapes, pagination and action endpoint before relying on it;
changing the URL alone is insufficient. Migration does not create a native timer.

## Console and price check

The authenticated console allowed an unsaved Secure Cloud / EU-RO-1 /
on-demand / A100 80GB PCIe selection. One offer showed 188GB host RAM and 16 vCPU,
GPU $1.79/hour and 100GB container disk $0.014/hour, with no persistent/network
volume selected. The console rounded the total to $1.80/hour. These observations
supersede the old public $1.59 GPU/hour planning price, not the approval limits.

Using the displayed component rates, the 3,000-second maximum models
`(1.79 + 0.014) * 3000 / 3600 = $1.503333...` **before tax/other charges**.
This is not an all-in quote or a guaranteed spending cap. Taxes and the final
funding total were not supplied by the inspected payment preview. The $10 credit
entry reached a card-details form; no card information was entered or saved and
the form was dismissed. Account-specific financial details are excluded here.

Stock changed during inspection: the selected PCIe offer became unavailable.
SXM availability is not permission to substitute it. The draft form also used
the default RunPod image, not the approved pinned base, so it was never a valid
launch request. No scheduled stop/terminate control appeared in the inspected
creation/override form. The advertised CUDA version is not an assigned host's
driver/MIG/isolation qualification. Refresh the exact offer at execution time;
this observation is not a reservation or a still-valid launch quote.

## Remaining preparation, separated from paid checks

| Item | Current evidence | Required before funding/launch |
| --- | --- | --- |
| Native expiry | Negative upstream evidence and failed live readback above | Provider-supported enforcement and independently readable persisted deadlines, or an explicitly approved different control/provider plan. |
| API and SSH access | Configuration pages inspected; no new key generated or registered | A concrete external owner host and protected secret connection first; then minimum necessary access with owner consent. Never copy browser credentials or put provider/Kaggle keys on the agent Pod. |
| Independent controller | One-attempt journal, watchdog and HTTP fixture tests exist | Deploy and qualify a durable owner process outside the Pod, with persistent journal, heartbeat and authenticated cleanup/readback. This chat executor and a temporary notebook are not such a host. No GitHub workflow currently implements one. |
| CPU workload/runtime | Prior Kaggle suite: 132 PASS / 0 skipped; offline runtime and official-wrapper CPU evidence retained | Keep tested source/input pins. These tests were not rerun for this report-only change. |
| Launcher and input activation | Generated GPU entry is deliberately blocked; receiver creates private staging only | Connect the pinned base/bootstrap, SSH transport, fixed logical input paths, read-only mounts, UID isolation and controller heartbeat. Keep activation CPU-testable before rental. |
| Frozen payloads | 246 wheels, eight task files, 16 driver files and eight model files total 28,893,806,642 bytes | Rebuild/rehash exact wheel/task inputs privately and qualify a sufficiently large staging or sequential-streaming path. Model payload remains undownloaded in this preparation. |
| Storage | Executor had 27,872,649,216 bytes free at inspection | A simultaneous local payload staging needs at least 1,021,157,426 more bytes even before base/runtime/temp files. Do not fill this disk with a speculative 23GB model download. |
| Price, stock, tax and credit | Volatile console quote; all-in total unconfirmed | Recheck exact SKU/region/image/100GB temporary disk, tax and existing credits only after technical gates pass. Funding is a separate owner decision. |

The real driver manifest was rebuilt in memory and its 16 existing private
files verified against the frozen source. Wheel/task/model manifest identities
were rechecked; this is not another transfer of their full bytes. All 35 previously
executed source/test hashes remain unchanged. No new long test suite is needed
for the report-only update.

Actual assigned GPU/driver/MIG, Pod mount and process isolation, internet SSH,
native-expiry acknowledgement, model loading/healthy serving, one task, deletion
and final billing can only be observed on the eventual approved allocation.
They are NOT RUN, and are not mislabelled as prerequisites that require an extra
paid trial. The necessary supported interfaces and CPU integration must exist
before that one attempt.

## Concrete next dependency

First obtain authoritative confirmation of a currently supported provider-native
deadline and readback path. Funding, extra keys, a larger disk or API v2 migration
alone cannot establish that guarantee. The existing $2/3,000s/single-attempt
authorization remains intact; no repeated GPU approval is requested here.

Prepared technical question for [RunPod support](https://contact.runpod.io/hc/en-us),
**not sent**:

> We are preparing one Secure Cloud on-demand A100 80GB PCIe Pod in EU-RO-1.
> Before funding or allocating, please confirm whether RunPod currently supports
> provider-side UTC stop and permanent-termination deadlines in the initial
> create request that continue to work if our controller disconnects. Which
> supported authenticated read endpoint returns the persisted deadlines?
> runpodctl #330 removed these options after non-enforcement; #331 is closed
> unmerged. Our read-only GraphQL check rejects the Pod expiry fields, and the
> current REST v2 schema has no equivalent. Please provide the supported API
> contract and enforcement status, or explicitly confirm that it is unavailable.

Do not send this inquiry, disclose account details, or change the approval's
control requirements without the owner's applicable authorization. No support
message or new external issue was sent in this audit.
