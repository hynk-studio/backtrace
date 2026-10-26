# Reduced nine-slot actual execution, 2026-10-26 KST

The accepted single allocation is **consumed and deleted**. All nine real-model
slots were attempted. Two original submitted patches were independently evaluated:
one passed and one failed. Seven slots had no submitted patch and remain
**NOT_EVALUATED**. The overall pilot is **INCOMPLETE**, with no effect estimate.
Owner-side evidence integrity passed; this is separate from scientific completeness.
No automatic paid retry is authorized.

## Actual outcomes

| Task | R0 | R1 | R2 |
|---|---|---|---|
| requests_7309 | TIMEOUT; no submission | COMPLETED; submitted patch failed 8 tests | TIMEOUT after original submission; retained patch passed |
| rich_3486 | INCOMPLETE; no submission; official session-timeout error | TIMEOUT; no submission | TIMEOUT; no submission |
| httpx_3672 | TIMEOUT; no submission | TIMEOUT; no submission | TIMEOUT; no submission |

All eight non-COMPLETED sessions retained the official error
`Agent exceeded session timeout (5 min)`. Preserve the raw distinction between
seven TIMEOUT labels and one INCOMPLETE label. The enclosing children exited 0
within 307.4 seconds without a 330-second parent kill. All nine namespace and
sandbox cleanup checks passed. No task was replaced or retried.

For requests_7309, the R1 patch is 692 bytes, SHA-256
`85d999101667ffac055a55e8db4ed99a6d9c2e1e81f8d70bdbb21a0255552f60`:
220 tests, 199 passed, 8 failed, 13 skipped. The R2 patch is 1,180 bytes, SHA-256
`c84d488554937e6e1072d51b63ef193bc4592ba97177def0b5a788ac5deb0201`:
220 tests, 207 passed, 0 failed, 13 skipped. Both original official verdicts agree
with the inherited research verdicts; neither candidate needed a version-skip exception.

R2 submitted through the original submit_patch path before the 300-second limit.
Its retained submission checkpoint's latest completed request was at 290.265 seconds.
The later session timeout remains a timeout. The already submitted bytes were
recovered unchanged, exported before deletion and evaluated after both deletion
receipts. This was not reconstruction of an unsubmitted working-tree diff.
The seven missing submissions were not evaluated and are not seven failed test runs.

Confirmed resolutions over fixed planned denominators are R0: 0/3, R1: 0/3,
R2: 1/3. Submission counts are 0/3, 1/3, 1/3 respectively. Three tasks and seven
missing evaluations do not establish general R2 superiority, an effect size or
training effectiveness. All nine denominators remain visible.

## Identity and limits

The owner's **진행하자** continued the already accepted reduced scope.
Qualified and executed source: `a8ae2765e9b57a408be3e3930b3a69a977601535`.
Successful first-attempt free qualification:
[40227646365](https://github.com/hynk-studio/backtrace/actions/runs/40227646365),
511 native Linux tests. All 182 operational file hashes still match that source.

- Contract: `93e17e7c04b9907ef44bb0b961af15596a91dc80d332a767e4923964a05b957a`.
- Permit: `owner-reduced9-20261026-0914`; state commit
  `078e7760aaf112b2efa8c66a6def9798ebe1ac82`.
- Owner: [40248465278](https://github.com/hynk-studio/backtrace/actions/runs/40248465278),
  first attempt, overall INCOMPLETE and workflow failure.
- Independent watcher:
  [40248422989](https://github.com/hynk-studio/backtrace/actions/runs/40248422989),
  first attempt, DELETED and workflow success.
- Attempt: `2d987dffb06f4446819c0c6feaafd432`; EU-RO-1 Pod `0a5nl1huxm2vmz`.
- Claim: `96658117e8ee3cef72fbe2d002c661704dbd35e490109a499bb00c91b93e113e`.

There was one provider create, one serving process and no top-up. Fresh account,
stock, source and quota checks preceded the claim. The separate watcher cached
and armed it before create. Live GitHub core quota was 4,958 remaining of 5,000,
above the required 880-call reserve until reset. Original six-task selection,
candidate bytes, scientific limits and v3 rules were unchanged. The new outer
scope binds nine slots; inherited raw v3/18-slot metadata remains historical.

Accepted limits: additional USD4.30, cumulative USD9.50, reserve USD0.50,
all-in USD2/hour and allocation-inclusive 7,740 seconds. Original credited funding
remains USD10, with prior-spend floor USD5.0062308114. All limits were respected.

## Independently checked evidence

Actual frozen-image installation passed 246 serving packages. CUDA/A100 checks,
verified 23,297,590,856-byte model transfer and real MODEL_INFERENCE readiness
passed. The native CPU agent closure remained 143 packages. Observed model
metadata matched the fixed path, bfloat16, tensor parallel size 1, maximum model
length 32,768 and disabled prefix caching. Installation-stage model_execution
NOT_RUN describes that earlier stage, not the later real workload.

All 189 admitted HTTP attempt hashes match the separate serving transport ledger.
No slot reached 50 requests; the maximum charged-tool count was 28, below 30.
At stop, active requests were 0 and all 189 were finished. The transport separately
recorded 8 errors and 4 cancellations; these counts do not establish a more
specific cause. Usage was complete for 181 requests and missing/invalid for 8.
Eight slot token ledgers were incomplete, so the aggregate token total is UNKNOWN.
Trace-only token totals must not replace full gateway accounting.

Worker orchestration is PASS because all nine slots were attempted without
infrastructure failure. Scientific evaluation is INCOMPLETE because only two
original patches were submitted. The input-acquisition envelope inherits the
incomplete callback status; its pinned input-byte checks passed.

The owner-side audit decrypted 152 retained and 163 exported records in memory,
verified candidate/task/patch/trace bindings and independently inspected 8 actual
JUnit XML files: six baseline/reference controls and two candidate patches. All
three paired controls passed the unchanged research protocol. The Rich reference
control retains the earlier official-false/research-true version-skip distinction.

| Event | Time on 2026-10-26, Asia/Seoul |
|---|---|
| Fresh idle account and exact stock observation | 09:13:29 |
| Independent watcher armed | 09:18:03 |
| Sole create request logged | 09:18:05 |
| First retained workload heartbeat | 09:36:45 |
| Encrypted export completed | 10:20:57 |
| Owner exact-ID deletion sent | 10:21:47 |
| Both independent second absence observations | 10:24:48 |
| Independent CPU evaluation began | 10:24:51 |
| Independent CPU evaluation ended | 10:25:49 |
| Final independent account observation | 10:25:56 |

Both owner and watcher proved DELETED with two complete absence observations,
bound to the same immutable claim and Pod. Export preceded both cleanup paths;
CPU evaluation began after both finished. Separate read-only workflow
[40254160991](https://github.com/hynk-studio/backtrace/actions/runs/40254160991)
also observed the exact Pod absent, the complete Pod list empty, autopay off and
current spend USD0/hour. Its 404 log endpoint means logs were unavailable after
deletion; it is not an additional failure of the deleted resource.

## Actual cost and remaining work

| Item | USD |
|---|---:|
| Balance before this allocation | 4.9937691886 |
| Additional actual spend | 1.9142661298 |
| Balance after deletion | 3.0795030588 |
| Cumulative spend from original USD10 | 6.9204969412 |
| Actual observed all-in hourly rate | 1.804 |

Remaining credit does not authorize another allocation. No stock monitor,
automatic paid retry, training, merge, Issue #1 closure or competition submission
was performed. The immediate observed limiting budget was the fixed five-minute
session: eight official timeout messages occurred before HTTP-count or charged-
tool-count ceilings. Further free work may inspect retained traces and design
prospective changes while preserving these outcomes. Operational changes require
renewed qualification; another paid attempt requires new owner authorization.
R3 remains separate and does not depend on a positive R2 result.

All 61 pre-task branch heads and 12 pre-existing free-state metadata blobs were
preserved. The only changed existing branches are this review and the reduced
state branch. New observation/start/watch branches belong to this accepted scope.
Retain initial invalid-YAML read-only observation 40247892946 and its corrected
successful observations. That failure created no jobs or provider resource and
did not alter the 182 qualified operational bytes. See the adjacent results JSON
for checked counts, hashes, verdicts, costs and deletion receipts.
