# Authorized one-case retry qualified; current stock prevents admission

The owner explicitly requested “다시 하자”. The corrected execution source
`08148b7245b772830319d3bdc90be3ad2c74ca51` is fully qualified, but the four fresh read-only observations
found no GPU satisfying the existing memory, price and remaining-budget rules.
No actual start, paid permit, claim, Pod POST, GPU training or generation occurred.
The new one-attempt authorization remains unused. This is not another HTTP400
attempt and provides no new reasoning result.

[Draft #55](https://github.com/hynk-studio/backtrace/pull/55) retains this work,
stacked on the error-recorder fix in #54. The first rejected attempt, its two
NOT_RUN outcomes and completed cleanup remain unchanged in #53.

## Completed qualification

[Run 41299786120](https://github.com/hynk-studio/backtrace/actions/runs/41299786120)
passed all four jobs at the immutable source above:

- All 775 native tests and Python CPU preflight; 32 focused tests also passed.
- Full pinned E2B checkpoint/tokenizer and both preassigned label-free inputs.
- The same selected example and training specification as the first attempt:
  1,357 prompt and 60 target/terminal tokens, 640 updates, 906,880 effective
  and 38,400 supervised training tokens.
- Tiny random-model CPU control: NLL 4.863375 to
  4.466372; exact trained-probe agreement after fresh-process
  reload, zero evaluation updates and corruption rejection.
- Ordinary-container isolation and independent free owner/watch deletion.

Verification checked 56 original archive members,
362 embedded source bindings across
110 paths, and all 110 Git blob identities. The frozen
historical provider client is unchanged. The trained CPU control is an
implementation check, not a pretrained GPU or reasoning result.

## Current admission blocker

| Account observation (UTC) | Credit (USD) | Pods | Admission |
| --- | ---: | ---: | --- |
| 2026-11-01T10:57:26Z | 1.1925423895 | 0 | No admissible offer |
| 2026-11-01T11:04:05Z | 1.1925423895 | 0 | No admissible offer |
| 2026-11-01T11:10:22Z | 1.1925423895 | 0 | No admissible offer |
| 2026-11-01T11:12:15Z | 1.1925423895 | 0 | No admissible offer |

The latest complete inventory was observed at 2026-11-01T11:12:24Z.
Hourly spend was zero and autopay off. The balance remained USD1.1925423895;
no additional RunPod debit was observed. Billing settlement can lag.
Continuation spend remains USD1.7135017444, with USD0.5864982556 remaining in the
USD2.30 envelope. The retry has the unchanged separate USD0.55 cap and projected
remaining-credit floor USD0.6060441339.

At the final observation, the available qualifying-size product was L40S at
USD1.09/hour. Including the fixed USD0.015/hour storage projection gives
USD0.9208333333 over the existing 3,000-second limit, exceeding both the retry
cap and remaining continuation envelope. L40 was briefly quoted at USD0.82/hour
(USD0.6958333333 maximum), also inadmissible. No allowed A40/A6000 route met the
current stock/quote checks. These are observations of queried routes, not a stock
reservation or a guarantee about later availability.

Nominal 24GB L4/4090 products were not admitted: the existing selector requires
nominal 40GB or more to preserve its fixed reported-device floor of 24GiB.
Their actual hardware was not allocated or measured here. No hardware threshold,
time limit, budget, provider request, training or scoring rule was relaxed.

## Unused scope and resumption

A complete remote state-tree inspection at 2026-11-01T11:14:05.797Z found no entries
under `minimum/reasoning-onecase-retry-paid-20261101/`, and the retry start ref
was absent. The state commit was `a55cd72617d0031ee573cb2b160da4f283a7b702`. Only the separate free
qualification state exists. The evidence receipt records the immutable state
commit/tree and matching refs; its absence results are filtered from a complete,
untruncated tree response. No background paid launch or periodic automation was
created.

The owner's retry instruction is still unused for this scope. Resume with the
qualified source `08148b7245b772830319d3bdc90be3ad2c74ca51`, refresh complete inventory/account/exact
quotes, and issue the fresh one-use permit only when unchanged admission passes.
Then create the new retry start ref at that exact source and continue through
collection, independent cleanup and post-cleanup scoring. Another confirmation
is not needed solely because stock was previously unavailable. A different
source requires its own complete qualification; a second paid create after a
consumed attempt remains prohibited without a new owner instruction.

The existing [research protocol](small-model-onecase-retry-20261101.md) remains
fixed. No held-out evaluation, top-up, main merge or Augnes write occurred.

Reproduce the retained evidence checks from this branch:

    PYTHONPATH=. python docs/evidence/onecase-retry-qualified-run-41299786120/verify.py docs/evidence/onecase-retry-qualified-run-41299786120
    PYTHONPATH=. python docs/evidence/onecase-retry-account-verification.py
