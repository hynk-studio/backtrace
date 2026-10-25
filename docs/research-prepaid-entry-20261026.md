# Research pilot preparation through the paid boundary

Status: **free preparation qualified; paid execution blocked by funding, stock
and a fresh explicit owner decision**. The owner requested work through, but excluding,
paid execution. [Draft #27](https://github.com/hynk-studio/backtrace/pull/27) is
stacked on #26 at `f7698ad6654c26bebaeb29d2e137d478d47ae55a`.

The executed source is `3632000d2d6f470a01f640ead7f4e2c8044805c6`, qualified by
[run 40214244082](https://github.com/hynk-studio/backtrace/actions/runs/40214244082).
The [machine-readable results](research-prepaid-entry-results-20261026.json)
bind all 176 operational files, the contract and artifact hashes. Result-only
documentation updates preserve those executed bytes. A future permit and paid
branches must bind this executed source and successful run.

## Completed free qualification

| Boundary | Observed result |
| --- | --- |
| Native Linux suite | 502 tests passed, including the actual dropped-UID permission regression |
| Frozen serving image | Full 246-wheel offline installation; pinned SSH server-only delivery and separate mutual TLS8443 |
| Native CPU tools | Unchanged 143-package closure; all 18 authored slots; 108 requests reconciled by order and body hash |
| Artifact identity | 177 private records and 315 exported records independently checked in memory; all 18 patches/checkpoints/agent inputs/traces matched |
| Controller lifecycle | One replica create, independent watcher armed before POST, encrypted export before both cleanup loops, two absence reads each |
| Live GitHub state | Separate owner 40214243989 and watch 40214244019 passed create-only and mutable-CAS handshake |
| Real account | Read-only complete Pod listing empty; current spend/hour zero; auto-pay disabled |

The new entry uses the existing Runpod REST v2 adapter and a separate GitHub
state branch. A create-only claim and cached independent armed acknowledgement
precede the sole create request. Ambiguous create replies are never retried;
absence cannot be inferred from failed reads or an early empty list. Owner and
watcher retain the exact cleanup identity through state loss. Native tests cover
lost/false acknowledgements, delayed visibility, unavailable state, concurrent
updates, owner/watch process loss, setup bounds, identity rejection, funded-spend
accounting and partial export retention. Prior full serving readiness, connection
loss and outer-kill controls remain recorded in the unchanged #25/#26 evidence.

The frozen Dropbear binary disables forwarding. Delivery uses pinned SSH22 and
inference uses separately mapped mutual TLS8443. The entry requires unique TCP
mappings, a matching direct SSH endpoint and distinct ports on the same host.
Only serving source/TLS server material reaches the inference container; tasks,
evaluator material and the TLS client key stay on the isolated native CPU host.

The owner prepares task inputs and the CPU runtime before allocation. Production
checks actual CUDA/VRAM before weights transfer, then exact model/cache metadata
before the fixed 18 slots. Authored readiness cannot satisfy production mode.
The original 300-second work / 30-tool / 50-request allowances and evaluator
amendment are unchanged. Incomplete slots stay in the denominator. Independent
CPU evaluation follows confirmed resource deletion.

## Failures retained and corrected

1. Run 40211991201 / source 25a53ed passed 491 Linux tests and serving setup,
   but its first workspace extraction failed with Permission denied. Umask077
   had removed traversal bits from ancestors. Explicit chmod0711 and the native
   UID65532 regression correct this while credential directories remain private.
   The initial account query succeeded but Pod listing failed on unstripped key
   whitespace; the constructor now strips it. The original run stays failed.
2. Run 40213108303 / source a5652cb passed 499 tests and all 18 authored slots,
   but its owner raised StateError during final retrieval. The original specific
   state error was not retained. A deterministic follow-up reproduced rejection
   of a heartbeat written during GET because the reader sampled time before GET.
   Sampling after GET fixes that reproduced race; the original failure is not
   conclusively attributed beyond its retained evidence. New fixed diagnostics
   and post-termination receipt recovery retain the primary failure and actual
   partial export. All 18 patches/inputs/checkpoints were recovered independently;
   remote request reconciliation was unavailable in that failed run.

Both failed runs retained encrypted evidence and both cleanup observers confirmed
deletion. The local replica now gives GitHub and provider requests independent
locks, so a slow Docker deletion cannot falsely block GitHub heartbeats. Scratch
focused tests passed with the native-UID case skipped on that host; scratch's
full legacy suite hit PID/UID/ensurepip limitations and did not complete. Native
CI above is authoritative. Transient local assertion/logger failures are retained.

## Concrete unpaid proposal

Use one A100 PCIe80GB, one inference server, 100GB temporary disk, no persistent
or network volume, and no automatic paid retry. Keep the frozen image, eight
model-file identities and 246-wheel closure. Maximum allocation-inclusive time:
10,800 seconds: setup4020, 18 child/parent envelopes6120, encrypted export360,
cleanup300. See the [full proposal](research-pilot-compute-proposal-20261025.json).

Read-only account/stock observation at **2026-10-25T17:11:00Z** found no
available exact A100 offer in the checked regions. The pricing scenario below
uses the last observed quote at **2026-10-25T16:54:51Z**, which is expired for launch.
It is not a current available offer.

| Item | USD usage credits |
| --- | ---: |
| Existing balance | 4.9937691886 |
| Previously observed usage, from USD10 credited funding | 5.0062308114 |
| Headroom under the unchanged USD8 cumulative ceiling | 2.9937691886 |
| Last observed compute quote + retained 100GB disk bound | 1.79/hour + 0.014/hour |
| Modeled full three-hour usage at that quote | 5.412 |
| Credit needed for that quote plus USD0.50 reserve | 5.912 |
| Additional credited funds for that minimum | 0.9182308114 |
| Full USD6 ceiling plus USD0.50 reserve target | 6.50 |
| Additional credited funds for the full ceiling | 1.5062308114 |

The fixed three-hour envelope does not fit the current credit balance or the
old cumulative ceiling. Proposed limits remain USD6 additional usage, USD2/hour
and USD12 cumulative usage; none is newly authorized. Each fresh permit must
state credited funding and a prior-spend floor so a top-up cannot erase prior
usage. The last priced regions were CA-MTL-3, US-MO-1; the latest
read found no exact available stock. Refresh account, stock and exact price
immediately before any approved create. The entry rejects a quote older than
300 seconds, so the retained price cannot authorize a later create.

These are credit arithmetic, not a credit-purchase checkout quote. Available
purchase denominations and applicable checkout tax were not determined or
authorized. Official pricing describes second-based compute/storage charges and
no ingress/egress fee; credit-purchase tax is separate from the credited balance.
The retained disk bound must also cover the live Pod cost. The controller and
independent watcher do not constitute a provider-native hard dollar limit.

## Exact stop boundary and remaining work

The new start/watch branches and `pilot-20261026/authorization.json` are absent.
All 59 baseline branch heads, historical state and consumed claims are unchanged;
only the review branch and a new free GitHub handshake branch were added. No GPU
allocation, paid watcher, model transfer/inference/training, top-up, merge, issue
closure or competition submission occurred. All 18 real-model slots are NOT_RUN.

What remains is an explicit funding/budget/single-use execution decision, followed
by fresh precreate observations and, if authorized, the bounded actual provider
network/CUDA/model/cache/18-slot run. Retain partial/negative outcomes, export and
delete first, then independently evaluate on CPU; an incomplete pilot receives
no effect estimate. R3 adapter compatibility/training remains separate and does
not require a positive R2 prompt result. It is outside this compute proposal.

Primary contract/pricing text inspected on 2026-10-26 KST; rendered text is not
presented as retained exact source bytes or as a live provider allocation:

- https://docs.runpod.io/api-reference-v2/pods/create-a-pod
- https://docs.runpod.io/api-reference-v2/pods/get-a-pod
- https://docs.runpod.io/api-reference-v2/pods/terminate-a-pod
- https://docs.github.com/en/rest/repos/contents
- https://docs.github.com/en/rest/git/refs
- https://docs.runpod.io/pods/pricing
- https://docs.runpod.io/accounts-billing/sales-tax
