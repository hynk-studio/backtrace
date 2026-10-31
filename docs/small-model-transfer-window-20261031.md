# Bounded E2B continuation after a measured transport control

The [screen-probe failure](small-model-screen-probe-result-20261031.md) and
[E4B attempt](small-model-e4b-result-20261031.md) both timed out while delivering
the same common runtime, before installation or model work. Retain both original
attempts, all assignments and their independent cleanup proofs. No historical
failure is relabeled a model failure or a confirmed network cause.

Free run [41222020645](https://github.com/hynk-studio/backtrace/actions/runs/41222020645)
at211620aa372efe2502cda13091a38ce786690ee6 compared the existing1MiB SSH receive
window with8MiB. Four identical64MiB transfers used ABBA order and100ms delay
on each direction of a loopback byte-stream relay. Both variants used the same
pinned Dropbear/keygen, strict host authentication and exact atomic file readback.

| Order | Window | End-to-end transfer seconds |
| --- | ---: | ---: |
| A | 1MiB | 20.248380844 |
| B | 8MiB | 4.366012611 |
| B | 8MiB | 4.319643273 |
| A | 1MiB | 20.401601499 |

The mean elapsed-time ratio was4.68012812. All payload and manifest identities
matched. [Evidence](evidence/window-control-run-41222020645/provenance.json)
retains both raw artifact members, verified ZIP/member/source hashes and
recomputed payload/manifest hashes. This supports a larger window for this
imposed-delay condition. The relay adds application-stream delay; it does not
emulate every TCP behavior or attest provider RTT, throughput, disk speed, or
the cause of either paid timeout. It made zero provider/model calls. It is not
full model qualification.

The candidate changes the daemon receive window to8MiB while keeping executable
hashes, authentication, privilege separation, worker restrictions, exact readback,
600-second full-transfer ceilings and independent cleanup. Numeric progress
records now distinguish local source verification, sender streaming, receiver
streaming, receiver readback and commit. A timeout preserves bounded typed
counters, elapsed time and process exits; arbitrary SSH stderr and payload text
are excluded. Counters are observations, not substitutes for verified readback.

Before either multi-GB transfer, one deterministic public256MiB transport-only
file must arrive with exact readback within12 seconds. Its hard transfer limit
is20 seconds. A slow, failed or incomplete probe stops before runtime delivery;
there is no transfer retry. Passing it does not guarantee full-payload completion.
The short payload is never a model input. The same gate runs in free qualification.

The prospective E2B scope keeps the exact20 untrained B1 Augnes inputs, four
train-only updates and first original B0 generation. No output has been received
for those scopes, and no prompt/denominator/target is changed. Total/work limits
are1,550/1,130 seconds, with the unchanged300/120-second cleanup/export reserves.
Maximum projection isUSD0.261; minimum post-projection credit remains
USD1.9060441339, preserving the current cumulativeUSD1 continuation ceiling.
At the latest observed balanceUSD2.1716099885, aUSD0.59/hour GPU plusUSD0.015/hour
storage projectsUSD0.2604861111. A more expensive or unfunded fresh quote is
refused before create. The USD0.50 absolute reserve and no-top-up rule remain.

The new start/state are `bt-001-e2b-window-start-20261031` and
`bt-001-e2b-window-state-20261031`, namespace`e2b-window-paid-20261031`.
An8MiB window and an early measured transfer gate justify reconsidering the
previous transfer-failure regions, without claiming a historical repair. Keep
the unrelated RTX A6000/US-TX-1 create-rejection exclusion. Hardware memory
admission is unchanged; no cheaper undersized GPU is silently substituted.
No new permit/start is issued until exact-source native qualification, current
balance/price admission, and review of the retained failure/control evidence.

Local checks passed59 focused tests, preflight and diff checks. An initial run
exposed three obsolete scope fixtures, which were corrected, and the existing
Work-host AF_UNIX denial. That kernel test remains unchanged for the required
full native run; the local focused rerun explicitly omitted it. Actual inference,
CUDA backward/update/save-reload, matched B2/S learning, additional main-model
review and workflow benefit remain unmeasured. Continue through actual outcomes;
this transport correction alone does not complete the objective.

## Preserved qualification failure and final affordability revision

The initial correction sourceb9a7abb0c104b7689107f7345636b66151f6a793
failed free run41222934662:684 tests ran in178.190 seconds with25 errors
from historical runtime-identity validation. The transport control helper was
one of the R012 protocol's105 frozen source files. Do not repin the historical
protocol or skip its checks. The current correction restores the historical
helper, SSH bootstrap and delivery files byte-for-byte. It uses a versioned
`tools/small_model_delivery.py` and `tests/small_model_transport_control.py`;
its8MiB bootstrap setting exists only within the scoped context, restored on exit.
Both original and current delivery versions retain their stream regression tests.
The original105-file protocol validation now passes.

[All four failed-qualification artifacts](evidence/window-free-run-41222934662/provenance.json)
are preserved, including original test errors, free owner/watch receipts and
checkpoint/input verification. Their ZIP/member bytes and170 nested source hashes
across85 unique paths match that source. No paid allocation occurred.

The17:07:50 account observation showed delayed billing:USD2.1716099885 credit,
zero spend and autopay off; the17:07:57 inventory had zero Pods. Relative to the
pre-L40S balance, the observed decrease is nowUSD0.2389607788; continuation
spend isUSD0.7344341454. The superseded1,720-second/USD0.290 draft would no
longer fit the unchanged credit floor. Before any new permit, shorten total/work
to1,550/1,130 seconds and cap projection atUSD0.261. The actualUSD0.59/hour
scenario projectsUSD0.2604861111. All21 assignments and four planned updates
remain unchanged; incomplete outcomes stay incomplete. A fresh check can still
refuse a price or balance change.

After isolation,77 focused transport/historical-protocol/target/contract checks
and three collector-scope/probe/permit checks pass locally, as do preflight and
diff checks. The full exact-source native qualification must run again.
