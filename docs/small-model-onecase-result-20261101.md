# One-case reasoning verification blocked at provider creation

Actual [run 41295195306](https://github.com/hynk-studio/backtrace/actions/runs/41295195306)
sent one Pod creation request and received HTTP400 before a Pod ID, hardware
check, training or generation. Both original BASE/Q4 assignments remain NOT_RUN.
This is an infrastructure rejection, not a negative reasoning result.

| Stage | Observed outcome |
| --- | --- |
| Exact-source native CI | 767 tests and CPU preflight passed |
| Pinned tokenizer | One case: 1,357 prompt + 60 target/terminal tokens |
| Planned training | 640 updates; 906,880 effective / 38,400 supervised tokens |
| Tiny random-model control | NLL 4.863375 to 4.466533; exact fresh reload |
| Actual GPU checks / updates / generations | 0 / 0 / 0 |
| Original assignments | BASE 1 and Q4 1, both NOT_RUN |
| Independent cleanup | Both controllers: NO_RESOURCE_OBSERVED, two final absence reads each |

[Qualification 41294192731](https://github.com/hynk-studio/backtrace/actions/runs/41294192731)
passed all four jobs at immutable source ca6d2ce07c19eef01f465a0c59fe85f4cbd487a2.
Verification checked 56 original qualification members
and 353 bindings across 107 paths.
Local full tests had 7 failures, 10 errors and 4 skips due to executor process/
capability restrictions and a different bundled pip wheel; that log is retained
separately. The pinned CI passed all 767 tests.

The fixed train-only temporal-revision case is
c97ef7d722c04a0dab309c49b13cabe2e67feabad96e05c344f78698f7da9e62.
The [prospective protocol](small-model-onecase-20261101.md) remains unchanged.
No supplied-answer formatting example, held-out label, model result or loss
participated in selection.

## Rejection and resource observation

- Claim: 2026-11-01T10:00:56.275Z, A40 in EU-SE-1.
- HTTP400 recorded: 2026-11-01T10:01:04.753Z.
- Owner final absence: 2026-11-01T10:47:47.810Z.
- Independent watcher final absence: 2026-11-01T10:47:53.882Z.
- Final complete inventory: 2026-11-01T10:47:55Z, zero Pods.

Account, inventory and quote were refreshed immediately before creation.
Compute was USD0.59/hour; storage-inclusive projection USD0.605/hour,
or USD0.5041666667 over 3,000 seconds, below the USD0.55 cap. The request builder,
API client and bootstrap bytes match the previous successful A40/EU-SE-1 run.
This does not identify the rejection cause; Low quoted stock alone is insufficient.

The executed client discarded response bodies. Exact-name and broader Pod audit
queries for 10:00–10:02 UTC returned HTTP200 with no entries, including a later
read-only check. The available logs do not recover a specific historical rejection reason.
The [official API](https://docs.runpod.io/api-reference-v2/pods/create-a-pod)
documents structured problem details and multiple HTTP400 causes; the status
alone does not distinguish capacity from a request rule.

Both controllers retained the original unknown-create observation window,
without shortening it on HTTP status. No Pod identity was observed. Complete
histories remain in evidence. Workflow failure is not relabeled as training success.

## Cost and evidence

Balance before/after: USD1.1925423895 / USD1.1925423895.
Observed RunPod debit: USD0.0000000000. Continuation debit:
USD1.7135017444; remaining envelope approximately
USD0.5864982556.
Hourly spend is zero and autopay off. Balance observations can lag settlement.

Independent verification checked 8 original attempt
archive members, 10 Git state blobs and
246 bindings across 107 paths.
The scoring file preserves two NOT_RUN denominators. Its zero counters are
missing-output bookkeeping, not measured accuracy. No trained adapter or generated answer exists.

Four read-only account reports and both pairs of empty audit queries were also
matched to their original machine-readable job stdout. They establish only the
observed balances, inventory and lack of returned audit entries.

The permit/start/claim/source are consumed and immutable. No second create,
top-up, main merge or Augnes write occurred.

## Follow-up and reproduction

The independently repairable evidence gap was fixed in
[Draft #54](https://github.com/hynk-studio/backtrace/pull/54): bounded, redacted
problem fields enter result artifacts while one-create behavior and cleanup stay
unchanged. Its separate validation cannot recover the old response or establish
reasoning fit.

The research gate still requires one complete correct free-generated training
answer. Resumption needs a fresh permitted scope, current stock/budget and exact
source qualification with the corrected recorder. The separate Augnes connection
blocker still prevents actual service-value comparison.

Run from this branch:

    PYTHONPATH=. python docs/evidence/onecase-qualified-run-41294192731/verify.py docs/evidence/onecase-qualified-run-41294192731
    PYTHONPATH=. python docs/evidence/onecase-paid-run-41295195306/verify.py
    PYTHONPATH=. python docs/evidence/onecase-account-verification.py
