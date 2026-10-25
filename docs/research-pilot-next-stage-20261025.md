# Next stage: one bounded 18-slot pilot

Status: concrete planning envelope, **not authorized or launchable**. The
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
The server-only delivery/start and provider lifecycle still need integration
before a paid proposal is ready for approval.

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
charges; require at least USD6.50 available credit and the approved cumulative
limit. A USD12 project cumulative stop would further reduce the usable budget
when previous settled spend exceeds USD6. The old USD8 stop remains active until
an explicit new decision. Do not top up or change account settings automatically.
No fresh balance or stock read was performed for this document.

## Work required before an approval-ready launch

1. Package and authenticate the new inference-only serving entrypoint. Rehearse
   its actual delivery/start/stop on free CPU using the frozen image and 246-wheel
   closure. Keep native tools/evaluator outside that payload; preserve the already
   qualified TLS endpoint and read-only initialized-cache metadata contract.
2. Integrate the 18-slot controller, encrypted export and independent provider
   cleanup/watch state under one new immutable, unconsumed namespace. Exercise
   network loss, failed readiness, parent death and exhausted remaining time on
   free replicas. Preserve NOT_RUN slots and reclaim killed workspaces before UID
   reuse; evaluate patches on CPU only after GPU deletion.
3. Qualify that exact source for free, then prepare a fresh quote/account read and
   a concrete capped execution proposal. No old branch, claim or paid permit can
   authorize this pilot. Actual GPU/model/cache readiness remains a gate within
   the proposed bounded allocation after explicit approval.

The R3 teacher/adapter track remains separate. A positive R2 prompt result is not
a prerequisite for a tiny training-compatibility experiment; neither this pilot
nor its budget includes training or a Kaggle submission.
