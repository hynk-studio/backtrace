# Provider connection and independent remote observation

Owner scope: authenticated connection/environment checks, remote watcher deployment,
and fresh pricing/balance. Date: 2026-10-27 KST. Refs #1; stacked on Draft #35 at
`c048ec313e5e6cf20dc0b802efa48f336854b46d`. GPU minimum remains NOT RUN.

Three separate free workflows execute the full native suite and exact-image
transport probe, an owner observation/quote job, and an independent remote watcher.
The latter two use a new source-scoped state branch, exact workflow/run identities,
different Linux boot identities and create-only/CAS records. They read the live
Runpod inventory before and after a real heartbeat-cessation control. No provider
resource is allocated or adopted. The observer's wire adapter refuses every
non-GET request. No authorization/claim/resource record can be written through
the new state adapter. These are bounded deployments, not an ongoing monitoring
service or an armed resource-deletion controller.

The payload is the 24 previously qualified files plus the unchanged original
GPU-baseline plan. Fresh mutual TLS 1.3 material delivers the pinned SSH binary,
strict host-key verification protects file transfer, and remote byte checks
reproduce the unchanged precheck plan. The default unprivileged digest-pinned
container is inspected for Python/tools/namespace access/cgroup headroom.
No GPU is exposed, no kernels/model code run and no full runtime is installed.
Transport success and a blocked execution environment must be reported separately.

Quotes cover up to eight selected 24–80GB GPU types and 32 regional pairs,
preferring Europe. Filters require one secure-cloud GPU, 32GB quoted host RAM,
eight vCPUs, 100GB temporary disk, CUDA >=12.8 and public IP. Actual free RAM,
exclusive UUID, BF16, host isolation and cgroup visibility remain unobserved.
Compute is compared with the existing proposed USD0.90 / 3,000-second ceiling;
USD1.00 total plus USD0.50 balance reserve remains a proposal, not permission.
The storage projection rounds the published USD0.10/GB/month up to USD0.015/hour
for 100GB using a 28-day month. It is not a provider invoice or tax estimate.

Primary documentation inspected for this stage:

- https://docs.runpod.io/api-reference-v2/overview
- https://graphql-spec.runpod.io/
- https://docs.runpod.io/pods/pricing

## Actual results and limits

The final operational source is `5aadac4d20ed14d4900f44124ece021e890ba08b`.
The [machine-readable evidence](small-model-provider-evidence-20261027.json)
retains archive/member hashes, source/payload bindings, exact native/local test
outcomes, actual quotes, independent state blobs and earlier failed attempts.

| Check | Observation |
| --- | --- |
| Final native qualification | [40359142948](https://github.com/hynk-studio/backtrace/actions/runs/40359142948): 632 tests in 151.543s, zero failures/errors/skips; CPU preflight passed |
| Live authenticated provider access | Passed; complete Pod inventory read by both independent runners |
| Remote observer deployment | Separate owner [40359142960](https://github.com/hynk-studio/backtrace/actions/runs/40359142960) and watcher [40359143080](https://github.com/hynk-studio/backtrace/actions/runs/40359143080), matching source and different kernel boot identities |
| Actual heartbeat cessation | Detected at age 36.645 seconds; owner acknowledged the remote observation |
| Remote state | Seven final-source canonical blob hashes verified; fifteen new free-state blobs across all attempts |
| New payload transport | Fresh mutual TLS, pinned SSH, wrong-host rejection and all 25 files / 369,631 bytes verified |
| Remote preparation | Reproduced the original precheck plan SHA-256 `eee72721e08b336492aeb661e607991e39173eb685e2be62d7ec8a3c89885009` |
| Execution environment | **BLOCKED** under the tested default unprivileged OCI configuration |
| Historical preservation | All 24 previous qualified source files and all 73 pre-existing branch heads unchanged |
| Independent artifact verification | Seven ZIP digests, all 17 members, 41 source hashes, 25 payload files and seven final-source state blob hashes |
| Provider allocation / mutation | Zero; GPU minimum, pretrained inference and training NOT RUN |

The observer ran on a separate native GitHub runner, read actual Runpod inventory,
detected cessation and **terminated after the bounded check**. It is not left
running continuously, and it cannot delete a resource. There was no current
resource to bind or clean up. A source/resource-bound independent cleanup
controller and its distributed loss/deletion qualification remain unfinished;
the earlier local watcher tests do not establish that missing property.

The exact-image CPU transport probe confirms code delivery/start, not a live
Runpod Pod's NAT, SSH endpoint or capability configuration. It observed:

- `unshare --net --pid --fork --mount-proc true` refused with Operation not permitted.
- The cgroup namespace hid ancestor memory limits; the original memory reader refused it.
- `bwrap` was absent.
- System Python was 3.12.3, while the prepared runtime requires 3.12.14.

The first two are structural prerequisites for the current native-host design.
Installing Python or bubblewrap alone does not demonstrate that they are fixed.
No privilege override, host-cgroup mount or weakening of the old checks was used.
The temporary CPU container was removed and two absence observations confirmed it.
The currently documented Runpod create schema has no listed privileged/capability
field; this is a documentation observation, not proof of all possible provider
configurations: https://docs.runpod.io/api-reference-v2/pods/create-a-pod .

## Fresh account and price observation

Account observation: **2026-10-27 01:27:56 KST**. Quotes were read through
01:28:06 KST. Balance **USD3.0795030588**, spend/hour **USD0**, auto-pay **off**,
and **zero Pods**. This matches the previous observed balance; no new provider
resource charge was incurred by these read-only operations.

The bounded query covered 32 GPU/region pairs across eight catalog types;
seven additional pairs were not queried. Nineteen exact responses had null
compute prices and were preserved as unavailable, never converted to free stock.
The following were actual filtered stock observations, not catalog-only prices:

| GPU | Region | GPU GB | Quoted host RAM / vCPU | Compute USD/h | Proposed 50-min compute + temporary storage |
| --- | --- | --- | --- | --- | --- |
| A40 | EU-SE-1 | 48 | 50GB / 9 | 0.59 | about USD0.5042 |
| RTX A6000 | EU-SE-1 | 48 | 50GB / 9 | 0.59 | about USD0.5042 |
| RTX 4090 | EU-CZ-1 | 24 | 143GB / 36 | 0.89 | about USD0.7542 |
| L4 | EUR-IS-1 | 24 | 55GB / 14 | 0.59 | about USD0.5042 |
| L4 | EUR-IS-2 | 24 | 100GB / 12 | 0.59 | about USD0.5042 |

The existing USD1.00 proposal plus USD0.50 reserve is funded by the observed
balance. That does not qualify these machines for the current execution design.
Stock is not reserved; nullable public-IP/count summaries remain nullable after
the exact query required one GPU and public IP. Measured available RAM, GPU BF16/
exclusivity and tax/other charges remain unknown. L40S USD1.09/h observations
exceed the separately proposed USD0.90 compute ceiling over 3,000 seconds, even
though their compute+storage projection is below USD1 total; no cap was relaxed.

## Retained corrections and next work

Initial source `62762cb1dd778f4db912459d802b8d8005c3c0ad` had an unquoted colon-space
in two workflow shell scalars. CPU run 40358353499 and owner 40358351590 failed
workflow parsing before job entry; watcher 40358356284 ended at its bounded wait.
Corrected source `a8affa02f945d7816e84020f8790aab7ab82fe81` passed 630 native tests
in 196.629s, exact-image transport and the live owner/watch handshake. Its quote
stage raised InvalidOperation. The original throw location was not retained,
so the nullable-price defect is an independently demonstrated correction rather
than a conclusively attributed original stack trace. The final source retains
partial account evidence and exception frames and treats null prices as unavailable.

Final local focused checks: 12 passed. The full local 632-test run retained five
failures, ten errors and four skips from the existing environment-sensitive
runtime/procfs tests. The full native 632-test run passed in 151.543 seconds,
with no failures/errors/skips; these environments are reported separately.
The earlier local 630-test attempt and all failed workflow artifacts are retained.

The next preparation must resolve the execution topology before spending credit:
either validate a native GPU environment that supports the current boundaries,
or implement and qualify a container-compatible GPU-only worker with the trusted
CPU coordinator/evaluator outside it. Preserve input/evaluator separation and
equivalent deadline/context cleanup evidence. Then bind an independent cleanup
controller to that exact source/resource, qualify its distributed failure cases,
and refresh account/quote/stock for a separately authorized hardware-only attempt.
The original precheck plan remains intentionally disabled and unchanged.
No merge, Augnes modification, training, submission or paid-claim reset occurred.
