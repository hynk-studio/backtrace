# E2B actual development result

Actual pretrained inference now works under the bounded worker. The result is
negative for the frozen synthetic contract and mixed for the three historical
Augnes examples. Strong prompting did not make this E2B configuration a reliable
diagnostic candidate. This does not establish that training cannot help or that
all small models fail.

Run [41206950960](https://github.com/hynk-studio/backtrace/actions/runs/41206950960)
used source `67f1b855d8bb2d5cffbe27087bce178e226e303d`, tree
`76586788a1156c388d342fd010cb708f1af5bc34`. Exact-source free run 41206225683
passed 688 native tests in 209.979 seconds and 17 container controls, including
the actual pretrained entry's refusal of missing GPU hardware. The original 18
assignments and six replay inputs reproduced their pinned token hashes before
allocation. All 24 returned wire identities, input hashes, output token IDs and
raw text matched their retained assignments. Independent post-deletion scoring
reproduced the complete recorded baseline report exactly.

## Execution and CUDA finding

A/B/C/D all passed actual BF16 matmul and SDPA with the passive Unix
sequenced-packet bind/listen correction. D still recorded one denied `connect`
call and exited normally. Thus denying connect did not prevent this run. The
changed allocation/driver environment and instrumented D prevent attributing all
historical failures to a single call. The earlier socket-only correction failed;
its original results remain in the first-attempt record. No CUDA initialization
was moved before restrictions. Process creation, exec, connect, accept, send,
other socket shapes and credential access remain blocked.

All 16 actual hardware checks passed, including active-context deadline,
transport and supervisor interruption followed by absent workers, idle GPU and
fresh kernels. The free container has 17 controls; these are different counts.
The full checkpoint loaded with no missing/mismatched text weights. The expected
unused audio/vision keys were allowlisted from its pinned tensor header.

The observed GPU was an A40. Loading took 2.607 seconds after staging; collection
took 150.674 seconds. Original assignments generated 1,204 tokens in 54.435 summed
worker seconds; replays generated 1,869 in 84.819 seconds. Peak model allocation
was 9,433,575,424 bytes and peak reservation 9,642,704,896 bytes. These measurements
do not establish RTX 4070 SUPER fit, cold download latency, concurrent headroom or
an end-to-end quality/speed advantage. Hidden host memory ancestry remains
unattested; no training or quantization was performed.

## Frozen synthetic scoring

| Arm | Returned | Syntactically valid JSON | Valid task response |
| --- | ---: | ---: | ---: |
| B0 | 9/9 | 8/9 | 0/9 |
| B1 | 9/9 | 9/9 | 0/9 |

These are nine related views of **one** development episode. Sixteen responses
failed the exact schema, commonly omitting active evidence IDs and returning an
empty posterior. B0 abduction contained malformed JSON; B1 abduction contained
an invalid probability value. Every assigned case therefore receives the frozen
invalid-response penalties, including decision regret 1 where applicable. This
is a complete negative protocol result, not a measured numerical reasoning error
conditional on valid answers. No intervals or population accuracy are claimed.
The collector's `OK` means syntactically valid JSON, not task validity.

## Augnes review against the precommitted rubric

The denominator is three author-selected retrospective episodes, with two prompts
each. The reviewer knows the historical outcomes. Five outputs are wrapped in
Markdown fences and therefore remain `INVALID_OUTPUT` under the frozen strict
JSON rule. Reading their content below is an explicitly descriptive semantic
review; it does not repair or reclassify those outputs.

| Episode | B0 | B1 | Rubric disposition |
| --- | --- | --- | --- |
| #1282 GET cancellation | LOCAL_FIX / HYPOTHESIS; fenced | LOCAL_FIX / HYPOTHESIS; strict JSON | Both should have retained DIAGNOSE / UNKNOWN. Both propose the already supplied observation of fetch owner, body settlement and cleanup, but posit a missing cancellation path without evidence. They do not explicitly distinguish the direct POST owner, and incorrectly treat one non-recurrence as conflicting evidence for their hypothesis. Neither establishes repair. |
| #1481 one non-recurrence | STOP_AND_RETAIN / UNKNOWN; fenced | STOP_AND_RETAIN / UNKNOWN; fenced | Both retain the original 9/1/6 non-deciding result, describe one bounded run, preserve unknown cause and consumed authorization, and propose no new Full or speculative behavior change. B0's candidate merely restates the stop condition. B1 adds an unsupported timing/settlement explanation and treats non-recurrence as conflict. Useful top-level restraint is largely copied from explicit input constraints. |
| #1549 readiness imports | LOCAL_FIX / HYPOTHESIS; fenced | LOCAL_FIX / HYPOTHESIS; fenced | Both separate readiness from invocation imports and request bounded changes with fresh-process checks. B0 explicitly preserves synchronous compatibility, binding/refusal and non-disclosure; B1 references the same F5 requirements. Neither clearly specifies lazy loading at the invocation boundary or independent positive detector controls. Both label the absence of a model call as conflicting evidence although it supports the import-coupling concern. These are proposals, not executed fixes. |

No incremental benefit over an additional main-model review, reviewer-time
saving, accepted suggestion, task resolution or specialist-learning effect has
been measured. Retain zero-hypothesis answers as allowed; the observed tendency
to manufacture a candidate even on a stop case is a development concern.

## Cost, deletion and next decision

Exactly one provider create produced Pod `yz5o9kijenjjdk`. Owner and independent
watcher each observed its absence twice. Owner deletion completed at 14:11:40
UTC, watcher at 14:11:13 UTC. The account read at 14:11:41 and complete inventory
at 14:11:48 found zero Pods, zero hourly spend, autopay off and USD 2.5524651839.
The observed decrease since the fresh pre-run USD 2.7121794034 is USD 0.1597142195;
cumulative observed continuation spend from USD 2.9060441339 is USD 0.3535789500.
These are credit observations, not a final invoice.

The capacity question now justifies the plan's conditional E4B comparison:
execute its deferred original 18 assignments and the identical six replay
messages with the same decoding/precision/worker limits. Preserve all E2B bytes
and strict scoring. One fresh exact-source qualification and single-use scope
must precede allocation. Maximum next projection remains USD 0.505, within the
remaining cumulative USD 1 ceiling and credit reserve. No automatic rerun,
top-up, training, production change or merge follows. The comparison can decide
whether to screen a usable untrained candidate or investigate bounded training;
this baseline's completion is not completion of the full research objective.

Raw collection, input schedule, scores, hardware/load records, cleanup and account
observations are retained in [the evidence directory](evidence/e2b-run-41206950960).
Its provenance file records both verified archive digests and every archive
member digest. Paid owner artifact 13045593226 SHA-256 is
`3cf77e40c69e5f68030365b0a0cc9a4f12f70c1f4e8330d4067e912061c0fb4d`;
watch artifact 13045795802 is
`1f9bf80b18ad563738713f8a6c1a297cec8ee747d3504e1fe29e38e7dac56c7e`.
