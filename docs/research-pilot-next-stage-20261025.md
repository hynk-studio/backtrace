# Next stage: one bounded 18-slot pilot

Status updated 26 October KST: free implementation and qualification complete;
**not authorized or funded for launch; no exact stock at the latest read**.
See [entry results](research-prepaid-entry-20261026.md). The
[machine-readable proposal](research-pilot-compute-proposal-20261025.json)
keeps six tasks and three arms and introduces no provider operation.

The first free exact-image probe (40156890457) pulled the correct digest but
stopped in the probe's tag-bearing RepoDigest comparison before container entry;
its cleanup helper also rejected the new name outside the existing owned-name
allowlist. Neither failure establishes a provider capability limitation. The
corrected probe uses the existing digest comparison and owned CPU-container name
contract; a new actual execution is required. The original failure is retained.

The corrected [actual probe 40157265702](https://github.com/hynk-studio/backtrace/actions/runs/40157265702)
entered the exact image and observed **BLOCKED**, before model/runtime transfer.
Native Linux namespace entry passed; default-OCI image entry as root failed with
`Operation not permitted`. The image lacks `ip`, and reports Python 3.12.3
(the independently qualified CPU evaluator is 3.12.14). Container cleanup passed
two absence reads. The run's Linux suite passed 453 tests. This is an actual
default-container replica result, not an observation of Runpod's capability profile.

**Next implementation decision:** retain original agent tools and evaluator in
the qualified native Linux CPU host, with the dedicated UIDs and namespaces
already tested. Run only the inference server in the frozen GPU image. Connect
the root-owned local request ledger to that server through authenticated pinned
transport; selected commands must never reach this endpoint directly. This
avoids depending on nested namespace privileges in the provider container.
The [bridge and failure-artifact implementation](research-split-runtime-20261025.md)
is now CPU-qualified at source `0a8332282d7fc79768e055f2637c26273dc8f5b6` in run 40163153274: 467 Linux tests,
18 normal authored slots, 136 transported attempts, retry/compaction, pre/post
submit work deadlines and an outer kill. This uses an exact-image TLS forwarder
with a native authored upstream and host networking; it does not establish
provider NAT or a running model. The pinned cache argument slice and official
server command are verified; initialized GPU cache state remains NOT_RUN.
The [server-only delivery/start/stop rehearsal](research-serving-lifecycle-20261025.md)
is now qualified in run 40206021955, including the full 246-wheel serving
closure, Docker bridge publication, all 18 authored slots and independent local
owner/watcher cleanup. That local rehearsal alone did not qualify distributed
entry. The new [entry qualification](research-prepaid-entry-20261026.md) now passes
the actual owner/watch code through HTTP replicas, plus two real GitHub state
workflows. Actual provider network/GPU/model behavior remains NOT_RUN.

## Proposed resource and cost envelope

Use one non-interruptible A100 PCIe 80GB, one model server, 100 GB ephemeral disk,
no persistent/network volume and no automatic paid retry. Pin the successful
image digest, all 246 runtime wheel identities and all eight model files,
including tokenizer and template. The 23,265,352,448-byte weights are inference
weights; this is not an adapter-training proposal.

| Allocation-inclusive phase | Maximum |
| --- | ---: |
| Boot, transfer/install and model readiness | 67 minutes |
| 18 children (330 seconds) plus parent teardown (10 seconds) | 102 minutes |
| Encrypted result export | 6 minutes |
| Provider deletion and independent absence checks | 5 minutes |
| Total | 180 minutes |

Each task still receives 300 seconds of work, 30 charged tools and 50 total
model requests. The child's remaining 30 seconds is setup/teardown allowance,
not extra model reasoning. Reserve another 10 seconds for parent namespace
reaping and workspace deletion after each child. Do not start a slot without
enough time for its full child/parent envelope and the export/deletion window.
Keep any remaining slots
as NOT_RUN in the 18-slot denominator. A partial pilot cannot establish an effect.

Proposed additional spend cap: USD6, at a fresh all-in quote of at most USD2/hour.
This is a decision ceiling, not a current price. Reject fixed/unknown additional
charges; require the fresh full-window quoted usage plus USD0.50 reserve and
the approved cumulative limit. USD6.50 funds the maximum USD2/hour ceiling.
A USD12 project cumulative stop would further reduce the usable budget
when previous settled spend exceeds USD6. The old USD8 stop remains active until
an explicit new decision. Do not top up or change account settings automatically.
A fresh complete read-only observation is now recorded in the
[26 October entry results](research-prepaid-entry-20261026.md): no current exact
stock; current balance and the old cumulative headroom are insufficient for the
full fixed envelope. The last quote is an expired scenario only. No top-up or
limit change was performed.

## Completed preparation and remaining decisions

The new distributed entry, one-create claim/independent arm, endpoint/cost/time
bindings, full serving/18-slot/export path and failure controls are now freely
qualified. The exact source, retained failures and independent evidence audit
are recorded in [the final entry report](research-prepaid-entry-20261026.md).

The remaining gate is the owner's explicit funding, budget and one-use execution
decision. Fresh account/stock/price and watcher checks still run immediately
before any approved create. Actual provider port mapping, CUDA/VRAM, model and
cache readiness must pass inside the bounded paid window before model slots.
All18 real-model slots remain NOT_RUN. Export and confirmed resource deletion
precede independent CPU evaluation; incomplete pilots have no effect estimate.

The R3 teacher/adapter track remains separate. A positive R2 prompt result is not
a prerequisite for a tiny training-compatibility experiment; neither this pilot
nor its budget includes training or a Kaggle submission.
