# One GPU attempt after the connected-path audit

The owner's instruction, **그래픽 자원 있는지 확인하고 진행하자**, authorizes
checking stock and proceeding once under the established budget and conditions.
This scope was recorded at 2026-10-22 13:44 KST; this is the record time, not an
assertion about the message timestamp.

- Authorization: `owner-connected-gpu-20261022`.
- Review branch: `bt-001-connected-gpu-smoke`, based on Draft PR #9 at
  `5bd2d4d9cd27b51ede825afa959be924701c5943`.
- Dedicated paid/watch branches: `bt-001-a100-start-connected-gpu` and
  `bt-001-a100-watch-connected-gpu`. Create only after renewed qualification.
- One A100 80GB PCIe Secure allocation, one server and one `fastapi_11194`
  public task. Frozen model/candidate/task/prompts and inference limits remain.
- Existing USD 10 wallet, USD 8 cumulative stop; no additional funding or
  Auto-Pay. Setup/useful/allocation-to-deletion limits: 5400/6900/7200 seconds.
- No automatic second allocation, recurring resumption, training, submission,
  merge, issue closure or publication of private plaintext.

## Fresh account and stock

Read-only job 119643734815 observed at **2026-10-22T04:44:29Z (13:44:29 KST)**:
zero account Pods, zero current hourly spend, Auto-Pay off and USD 7.2408300035
balance. The previous owned Pod is absent. Broad stock shows CA-MTL-3 and
EU-RO-1; the exact filtered single-GPU CA-MTL-3 quote qualifies at USD 1.79/h
compute plus USD 0.014/h temporary disk. The two-hour maximum is USD 3.608;
including observed previous spend, USD 6.3671699965 is below the USD 8 stop.
This is a point-in-time quote, not a reservation or final invoice. The controller
must refresh it immediately before a create. Original observations are in
`a100-connected-gpu-stock-20261022.json`.

## Qualification and prevention checks

The completed free audit at `47f27dc15908f9562993e214e4be786cbafe11fd`
established the actual driver/HTTP/all-tools/delegation/patch/recovery and public
verifier controls on host and exact offline image. It did not establish GPU
generation, Gemma parser behavior or model performance.

The fresh namespace and branch identities change qualified operational files.
The old receipt must fail closed until the full free qualification is renewed.
The binding also includes the paid entry, offer checker, start/watch workflows
and their existing gate tests, so later changes cannot silently reuse that
receipt. The prepared driver and scientific inputs remain byte-identical to
the successful connected audit. All historical claims and paid/watch heads
remain consumed and immutable.

Require a successful new full qualification, exact-source Linux CPU checks,
free owner preparation and a fresh matching independent watcher before the
single create. Success requires real task artifacts and byte recovery, followed
by independent Pod-absence/account checks. Evaluate recovered model output
separately on free CPU only after cleanup; a verifier infrastructure error is
not an unresolved model score.

Initial state: qualification renewal pending; provider allocations: **0**.
