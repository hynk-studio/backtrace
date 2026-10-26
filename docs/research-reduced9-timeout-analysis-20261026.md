# Reduced pilot timeout review and prospective comparison, 2026-10-26 KST

This is an unpaid inspection of the original, encrypted results from the
single-use [nine-slot execution](research-reduced9-execution-20261026.md).
It does not rerun the agent, model, evaluator or provider workflow. The original
source `a8ae2765e9b57a408be3e3930b3a69a977601535`, raw slot statuses,
submitted patches and [result receipt](research-reduced9-execution-20261026-results.json)
remain unchanged. This document is a prospective design note, not a replacement
for the fixed v3/reduced9 protocol or a new paid permit.
The [sanitized timing receipt](research-reduced9-timeout-analysis-20261026-metrics.json)
records slot-level counts and original trace hashes without task, prompt,
model-response or patch contents. The owner export's SHA-256 was checked and
decryption occurred in memory. Gateway records give response-finish elapsed
times; ATIF traces give structural tool events and elapsed times.

## Observed boundary

All nine slots were attempted with 300 seconds of agent work, at most 30 charged
tools and 50 model requests each. The enclosing 330-second child allowance
includes teardown; it never adds 30 seconds of reasoning. Seven raw slots are
TIMEOUT, one is INCOMPLETE and one COMPLETED. Each of the eight non-completed
sessions carries the official `Agent exceeded session timeout (5 min)` error.
None reached the 50-request cap, and the maximum charged-tool count was 28.
There was no 330-second child kill. These facts locate the immediate limiting
boundary at the agent session, without proving which activity consumed its time.

Only `requests_7309` R1 and R2 submitted an original patch. R1 completed, but
its patch failed eight independent tests. R2 submitted before the 300-second
deadline (last completed request in its submission checkpoint: 290.265 seconds)
and the original patch later passed all 207 non-skipped tests. Its later agent
TIMEOUT remains a timeout. Seven other slots had no original submission and
remain NOT_EVALUATED, not failed public test runs. The confirmed resolution
counts R0 0/3, R1 0/3 and R2 1/3 are descriptive only; there is no paired effect
estimate or general treatment conclusion.

The run reconciled 189 forwarded model HTTP attempts, eight transport errors
and four cancellations. The receipt does not attribute a slot's timeout to
those events. Usage was complete for 181 requests and missing/invalid for eight;
eight slot token ledgers are incomplete and the aggregate token total is
unknown. Equal maxima do not establish equal realized inference cost.

| Slot | Raw status | HTTP 200 / attempts | Charged tools | Last HTTP 200 (s) | Largest successful response-finish gap (s) | First edit/write (s) | Submit (s) |
|---|---|---:|---:|---:|---:|---:|---:|
| requests R0 | TIMEOUT | 24 / 25 | 24 | 291.3 | 30.8 | 80.8 | — |
| requests R1 | COMPLETED | 31 / 31 | 28 | 246.5 | 24.1 | 224.3 | 238.2 |
| requests R2 | TIMEOUT | 30 / 31 | 28 | 290.3 | 32.2 | 178.4 | 290.7 |
| rich R1 | TIMEOUT | 17 / 18 | 16 | 186.1 | 32.2 | — | — |
| rich R2 | TIMEOUT | 19 / 20 | 18 | 249.8 | 60.2 | 159.3 | — |
| rich R0 | INCOMPLETE | 22 / 23 | 21 | 299.0 | 75.4 | — | — |
| httpx R2 | TIMEOUT | 15 / 16 | 14 | 288.4 | 70.7 | — | — |
| httpx R0 | TIMEOUT | 12 / 13 | 11 | 287.7 | 73.4 | 171.1 | — |
| httpx R1 | TIMEOUT | 11 / 12 | 10 | 271.7 | 82.4 | 248.3 | — |

Times are elapsed relative to each 300-second session and rounded to 0.1 s.
All eight non-completed slots had one final non-200 attempt with missing usage;
the accounting ledger closed every attempt and had zero active requests at stop.
The gaps measure successive **successful response finishes**, including other
agent and tool work. Request start timestamps were not retained, so these are
not measured API or generation latencies. Trace and gateway clocks have nearby
but distinct origins; a cross-clock subtraction is approximate. In particular,
Rich R1 had no valid response after 186.1 s, leaving 113.9 s until the limit,
but that interval cannot be attributed wholly to model or network delay.

Four of the seven non-submitting slots show a recognized edit/write event and
three show none. Such an event does not prove there was a viable patch; no
unsubmitted working-tree diff was recovered as an original submission. Requests
R1 edited at 224.3 s, issued two later commands and submitted at 238.2 s.
Requests R2 last edited at 279.1 s, issued a later command and submitted at
290.7 s; its next request ended without a valid response around the deadline.
This distinguishes a correctly preserved predeadline patch from the raw later
timeout. The common R0 prompt already mentions `submit_patch` twice, and
R1/R2 add verification-reserve language. Merely repeating the submission tool
name is not a demonstrated remedy. The trace did not retain enough information
to separate reasoning, generation, transport and framework time causally.

## Prospective common-arm procedure

1. Freeze a **new version** before any further model observation. Keep the
   already observed nine slots, fixed task identities, patch bytes and evaluator
   verdicts as the original reduced9 outcome. Do not rescue only seven missing
   slots, treat a rerun as a continuation of those sessions, or select a task
   based on this favorable or unfavorable result. A repeat of an inspected task
   is a diagnostic/repetition and needs that label.
2. Draft a shared 210-second exploration cutoff and 270-second target for an
   original submission, leaving up to 90 seconds for finalization and 30 seconds
   for response/final status before the unchanged 300-second hard deadline.
   Apply the same status check, current-diff inspection and feasible relevant
   bounded check to R0/R1/R2. Reserve up to six charged tools for this phase,
   as already described for R1/R2. Report
   unfinished or failed checks honestly; never invent a patch merely to fill a
   submission slot. Keep the
   substantive R1 generic-review and R2 diagnostic additions as separate,
   nested interventions. The existing common guidance already mentions status
   and submission, and R1/R2 already have a 90-second/six-tool reserve; a new
   common checkpoint requires deduplicating and rehashing those prompts. This
   is a hypothesis about scheduling, not evidence that it would solve Rich or
   HTTPX. A final unanswered model call could still cross a prompt-only
   checkpoint; prospectively specify and free-test a common in-flight request
   bound before implementation. It changes the candidates and cannot be read
   back into v3 results.
3. Retain the same 300-second, 30-tool and 50-request ceilings across every
   arm, including delegation, retries, diagnostics and compaction. Raising the
   session limit would require a separate protocol and operational redesign:
   the official five-minute configuration, gateway's 300-second maximum,
   330-second child boundary and allocation budget are currently coupled.
   Do not silently call a longer run matched to this pilot.
4. Before any future claim, version and bind candidate prompt/archive hashes,
   protocol, task selection, order, source, evaluator rules, maximum total
   allocation time and cost. Qualify the changed complete path on free CPU,
   including actual original-tool submission, time-limit/parent cleanup,
   request accounting, encrypted export and independent post-deletion evaluation.
   Fixture-model success tests the plumbing only. Retain every assigned slot,
   timeout and missing usage counter; report official agent completion and
   independent patch correctness separately. A strict total-token comparison
   still requires complete usage coverage.

The original six-task/18-slot campaign was never run as a whole. Its first
three selected task-arm combinations per repository were observed in this
separate reduced amendment; the other nine combinations were not run. A future
comparison needs whole task triads and a prospectively fixed order/sample,
with any reused tasks identified as previously observed. R3 feasibility remains
a separate decision and does not require positive R2 evidence.

## Funding and decision gate

The account read at 10:25:56 KST found USD3.0795030588 remaining, zero Pods,
zero current spend and autopay off. After the existing USD0.50 reserve, at most
USD2.5795030588 of that observation is available before any other constraint.
The old conservative nine-slot bound is USD4.30 (7,740 seconds at USD2/hour),
which this balance cannot cover. At that hourly ceiling even the old fixed
4,020-second setup plus 360-second export and 300-second deletion reserves cost
USD2.60, before any of the nine 340-second slot/parent allowances. The actual
USD1.9142661298 past spend is not a fresh quote, a revised worst-case bound or
authorization to create another Pod.

This free design does not change provider settings or reset the consumed claim.
Any future paid proposal must define a different affordable, fully qualified
scope or new credited funding, obtain fresh stock/price/account checks and a new
owner authorization. Do not merge, close Issue #1, submit to the competition or
start R3 training as a side effect of this analysis.
