# Changing-state evaluation and development baseline preparation

Scope: continue A1 from [Draft #30](https://github.com/hynk-studio/backtrace/pull/30)
at `31d02bb9826889deb8f188fa0e0e1562d436295f`. The prior teacher, benchmark,
scorer, protocol, tests and CPU evidence stay byte-identical. This extension
provides CPU evaluation instruments and prompt packets. **No student model has
run, no training has run, and no capability improvement has been measured.**

## What the temporal task adds

The old revision task changes evidence about a fixed world. The new task unrolls
a supplied finite state process: five original variables at time 0, a selected
cause at times 1 and 2, and a noisy time-2 sensor. There are eight Boolean
variables and at most 256 worlds. Exact enumeration remains the reference.
Transitions cover persistence, uncertain changes, independence, a forced change
and asymmetric drift. Temporal edges can be ineffective in independent or
deterministic settings; family membership deliberately remains the original
five-node problem family, not a newly claimed effective temporal topology.

Four information cutoffs expose an old signal, its duplicate, a delayed old
cause observation together with a current signal, then an explicit retraction
and correction of the current signal. A future record remains unavailable.
The target state time is always 2; availability cutoffs 2–5 change what is known
about that fixed target, not the state horizon. An observation of an event must
carry that event's exact state time. Delayed past evidence is never relabeled
as a current measurement. Opposite values of different time-indexed states can
be consistent; conflicting active values of the same event are inconsistent.

The response estimates past/current cause probability and the probability that
the past and current states differ. It lists active evidence IDs and chooses a
one-step current-state check with actual contingent actions, or stops. Scores
include each temporal posterior error, decision regret, status/evidence errors,
duplicate invariance, update direction and correction direction. Direction
checks also penalize unnecessary reversal of a target whose reference is
unchanged. Missing/invalid answers and wrong abstention retain maximum applicable
loss; only reference status excludes undefined numerical endpoints. Family
means and case means are separate, including for paired endpoints.

See the [temporal protocol](temporal-evaluation-protocol-v1.json). This is inference
under a **supplied transition model**, with one check then one action. It does
not infer an unknown transition law, discover absent causes, or solve multi-step
planning. There is no claim of empirical calibration or real Augnes usefulness.

## Data and prompt comparisons

All temporal views reuse the original family and episode IDs and partition.

| Partition | Families | Episodes | Original rows | Temporal rows |
| --- | ---: | ---: | ---: | ---: |
| Training | 12 | 240 | 1,200 | 960 |
| Development | 8 | 160 | 800 | 640 |
| Reserved candidate | 20 | 400 | 2,000 | 1,600 |
| Total | 40 | 800 | 4,000 | 3,200 |

The combined 7,200 rows are **800 episodes in 40 family groups**. Rendering and
snapshot copies are not independent samples. These remain candidate partitions;
development model measurements, power analysis and final test sealing are pending.

The [baseline preparation protocol](abductive-baseline-protocol-v1.json) creates
four packets over the same 1,440 development inputs: B0/minimal versus B1/guided
prompt, each as JSON or controlled English. Both arms have the same precise
task/output contract; B1 adds evidence, revision and decision-check guidance.
Both backbones reuse the packets. Later B2/general SFT and S/specialist SFT use
the same B1 runtime prompt within each backbone. The controlled text preserves
the model, CPT parent-value associations, evidence IDs, times, hypotheses,
payoffs and inspections; it is a template rendering, not uncontrolled natural
language, distracting claims or a real Augnes record.

Only isolated **development input exports** are accepted. Training/reserved
exports and directories with extra files are rejected. The compiler reads no
evaluator labels and performs no exact solve. Tests trap those reads/calls.
IDs are transport fields outside the system/user messages. No answer, family,
episode or manifest content enters messages. Train-only temporal exports use
training labels only. File projection is not an OS sandbox; a future runtime
must receive only the projected input packet, not the dataset or this repository.

Packets are **PREPARED_NOT_EXECUTABLE**. Exact model/tokenizer revisions,
chat-template and role mapping, precision/dependencies, real token counts and
hardware feasibility are unmeasured. Proposed input/output ceilings are
12,288/4,096 tokens, greedy decoding, one response, no tools or retries. These
are experimental limits to qualify, not claimed model limits. A tokenizer or
template incompatibility, or overflow, requires an explicit matched design
revision before execution; never truncate or silently remove cases.

The full candidate grid is 5,760 responses per backbone (11,520 for both),
**none executed or authorized as a paid run here**. A smaller development
screening batch may be fixed before results when constructing an affordable
runtime scope. Preserve raw outputs, token usage, termination reasons and
latency; malformed/truncated answers remain in the assigned denominator.
Preparation alone is neither a baseline result nor a training effect.

## Reproduce

Use new destinations; source changes invalidate temporal manifests. The original
v1 manifests remain valid because their four bound sources are unchanged.

```sh
python3 -m unittest discover -s tests -p 'test_temporal_baseline.py' -v
python3 -m tools.temporal_benchmark generate .local/new-temporal --variants 20
python3 -m tools.temporal_benchmark audit .local/new-temporal
python3 -m tools.temporal_benchmark export-training .local/new-temporal .local/new-temporal-train
python3 -m tools.temporal_benchmark export-inputs .local/new-temporal .local/new-temporal-dev --split development
python3 -m tools.abductive_benchmark export-inputs .local/existing-v1 .local/new-static-dev --split development
python3 -m tools.abductive_baseline .local/new-baseline --view .local/new-static-dev --view .local/new-temporal-dev
python3 -m tools.temporal_scoring .local/new-temporal .local/predictions.jsonl --split development --output .local/new-temporal-score.json
```

Scoring is evaluator-side and reads the references. Prediction JSONL uses the
existing `id`/`response` envelope. An empty prediction file is a missing-response
control over the full assigned partition. Controlled-English responses use the
same IDs and scorer as JSON; report rendering effects separately.

## Validation and next gate

Initial focused run: 20 tests, one failed negative-control assertion. The test
mutated the oracle answer's posterior dictionary while it still aliased the
test reference, changing the expected answer too. Deep-copying the negative
response before perturbation corrected the test fixture; the scorer was not
relaxed. The repeated focused run passed all 20 tests in 26.006 seconds.
Analytic witnesses independently check late-old versus current evidence,
independent/persistent/forced transitions, smoothing, contradiction versus
zero support, retraction, real decision regret, and deliberately wrong
fixed-world answers. Generated controls cover all 40 graph families and all
five transition modes. CPU preflight reports READY.

Final focused qualification passed **21 tests in 24.796 seconds**. Native Linux
[run 40290483458](https://github.com/hynk-studio/backtrace/actions/runs/40290483458),
attempt 1 at source `714e09aac73cd817834916744073d1414cae1df0` (tree
`4eabd39823432884231635af60553e0723ef0c65`), passed **554 tests with no failures,
errors or skips** in 138.903 seconds, CPU preflight, both complete datasets,
exports, all-partition oracle/missing-response controls and all four development
prompt packets. The [CPU receipt](temporal-baseline-cpu-20261026.json) records the
executed source, data/exports/prompts and initial failures. The downloaded
artifact matched GitHub's digest; all 12 members and nine scientific source
hashes were verified. Local and native data, export, prompt and control summaries
were byte-identical. The follow-up commit changes documentation only. No model
result is implied by authored oracle or missing-response controls.

The initial local full suite ran 553 tests in 107.888 seconds and failed with
5 failures, 10 errors and 4 skips. The new 20 tests passed; failures/errors were
in the existing pip bootstrap fixture and procfs/PID-namespace cleanup checks,
as in the prior A1 local run. These are retained, not converted into a pass or
fixed by weakening operational guards. A further independent family-weight
test was added for the final qualification (21 new tests / 554 total).

Next: pin the independent E2B/E4B model and tokenizer/runtime identities,
tokenize these actual packets, define a bounded development screening run and
measure feasibility before training. Broader E2 hypothesis/model construction,
real-language/record transfer, power analysis and final confirmatory sealing
remain unfinished. No Augnes changes, paid allocation, merge, issue closure or
competition submission belongs to this step.
