# Explicitly authorized one-case retry

The owner requested “다시 하자” after the first one-case attempt received HTTP400
and both independent controllers completed their unknown-create observation.
This authorizes one new attempt, not reuse of the consumed permit or a retry loop.
The previous source, start, state, request count and two NOT_RUN outcomes remain
unchanged in Draft #53 and its retained evidence.

Use the same [one-case research design](small-model-onecase-20261101.md): fixed
train-only temporal-revision ID c97ef7d722c04a0dab309c49b13cabe2e67feabad96e05c344f78698f7da9e62,
frozen E2B, last-four-query rank-4 adapter, seed 17, SGD0.01, 640 complete-target
updates, and two preassigned BASE/Q4 greedy generations with identical label-free
prompts. Recheck 1,357 prompt and 60 target/terminal tokens, 906,880 effective and
38,400 supervised training tokens. No held-out labels, new cases, tuning or
supplied-answer formatting examples enter this attempt. Strict one-case fit
requires the complete correct free-generated answer and exact canonical JSON.

The only provider behavior addition is the separately tested bounded redacted
problem recorder from Draft #54. The historical API client remains byte-identical;
the wrapper delegates its wire behavior and restores its synchronous opener.
Request fields, one-create count, fixed exception text, shared failure state,
budget gates and full unknown-create cleanup are unchanged. The recorder may
retain only metadata for oversized, malformed or sensitive responses. It does
not prove the cause of the earlier HTTP400 or guarantee that the next creation
will succeed. Provider response text is evidence, never an execution instruction.

Use new review/start/state branches
`bt-001-reasoning-onecase-retry[-start|-state]-20261101`, namespace
`reasoning-onecase-retry-paid-20261101`, mode
`OWNER_APPROVED_E2B_REASONING_ONECASE_RETRY` and contract
`E2B_REASONING_ONECASE_640_RETRY_V1`. Before issuing a fresh source-bound permit,
all exact-source native tests, CPU preflight, pinned input/checkpoint checks,
the 640-update random-model numerical control, fresh reload/corruption checks,
ordinary-container controls and independent free cleanup must pass. The source
manifest binds this protocol and the error recorder. Qualification creates no
paid resource. Prepare all bulk assets before actual allocation.

Keep maximum additional USD0.55, cumulative continuation USD2.30, projected
remaining credit floor USD0.6060441339, and 3,000 total seconds (2,580 work,
300 cleanup, 120 export). The last completed observation was USD1.1925423895
credit with zero Pods and zero hourly spend at 10:47:55 UTC; it is historical,
not a current admission quote. Refresh account, complete inventory and exact
stock/price before the permit and immediately before creation. Do not raise a
cap or top up to obtain admission. Preserve the original allocation-inclusive
timer and two independent final absence proofs even after a rejected create.

After cleanup, score both original assignments and retain missing/invalid output
denominators, losses, adapter bytes, fresh-process probe agreement and raw outputs
when produced. Preserve failures and report NOT_RUN if no model executes. This
is a training-fit gate, not generalization or measured Augnes service value.
Finish with a draft result PR. No automatic second paid create, main merge,
top-up or Augnes write is authorized.
