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

## Proposed resource and cost envelope

Use one non-interruptible A100 PCIe 80GB, one model server, 100 GB ephemeral disk,
no persistent/network volume and no automatic paid retry. Pin the successful
image digest, all 246 runtime wheel identities and all eight model files,
including tokenizer and template. The 23,265,352,448-byte weights are inference
weights; this is not an adapter-training proposal.

| Allocation-inclusive phase | Maximum |
| --- | ---: |
| Boot, transfer/install and model readiness | 70 minutes |
| 18 fresh task children, each at most 330 seconds | 99 minutes |
| Encrypted result export | 6 minutes |
| Provider deletion and independent absence checks | 5 minutes |
| Total | 180 minutes |

Each task still receives 300 seconds of work, 30 charged tools and 50 total
model requests. The child's remaining 30 seconds is setup/teardown allowance,
not extra model reasoning. Do not start a slot without enough time for its full
child envelope and the reserved export/deletion window. Keep any remaining slots
as NOT_RUN in the 18-slot denominator. A partial pilot cannot establish an effect.

Proposed additional spend cap: USD6, at a fresh all-in quote of at most USD2/hour.
This is a decision ceiling, not a current price. Reject fixed/unknown additional
charges; require at least USD6.50 available credit and the approved cumulative
limit. A USD12 project cumulative stop would further reduce the usable budget
when previous settled spend exceeds USD6. The old USD8 stop remains active until
an explicit new decision. Do not top up or change account settings automatically.
No fresh balance or stock read was performed for this document.

## Work required before an approval-ready launch

1. Run the new runner and isolation prerequisites in the exact GPU image. In
   particular, native GitHub Linux PID/network namespace success does not prove
   those capabilities exist in a provider container. Determine deployment
   feasibility before a model transfer; do not silently remove isolation.
2. Qualify cache fairness using the pinned server implementation. The proposed
   setting disables cross-slot prefix caching while retaining a fresh task-local
   ADK conversation/cache. A command-line flag or reset endpoint is not assumed
   supported without inspecting and executing that version's path.
3. Exercise full-runner timeout both before and after actual submit_patch, plus
   outer-child termination. Preserve submitted patches and traces if available;
   explicitly report unavailable unsubmitted diffs. Current completed fixtures
   do not establish these failure outcomes.
4. Integrate 18 sequential children, accounting, encrypted export and independent
   cleanup with one new immutable authorization namespace. Reuse no paid claim
   or historical start/watch branch. Evaluate patches on CPU after GPU deletion.
5. Qualify that exact source for free, then obtain a fresh quote/account read and
   present the final bounded proposal for approval. Recompute usable budget from
   the account and cumulative stop; this document cannot mint a launch permit.

The R3 teacher/adapter track remains separate. A positive R2 prompt result is not
a prerequisite for a tiny training-compatibility experiment; neither this pilot
nor its budget includes training or a Kaggle submission.
