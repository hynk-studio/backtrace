# Competition contract: partial primary-source verification

Inspected on 2026-09-29 Asia/Seoul (2026-09-28 UTC). This is a dated source review,
not certification of a runnable submission. [Source records](source-manifest.json)
contain URLs, access windows, artifact IDs and actual-byte SHA-256 values.

## Evidence acquired

The six Issue #1 URLs returned HTML shells through HTTP; the web reader extracted
no body (the model/harness URL returned a reader error). Their hashes identify
those shells, **not** the contract. A normal rendered browser then exposed the
overview/model section, rules, data description, notebook and organizer welcome.
No authentication, terms acceptance or access-control bypass occurred. Rendered
text was read, but no byte snapshot was retained; those records have null hashes.
No search-index snippets are used as verified requirements.

The public [notebook API](https://www.kaggle.com/api/v1/kernels/pull/ryanholbrook/getting-started-gemma-4-developer-agent)
returned organizer notebook ID **135692529**, version **2**. The entire source was
read, not executed. Decoded UTF-8 notebook SHA-256:
`0c54c3bac3269e422b1d48ac8087ff26b49fe764231b7983c90ef842382f9a87`.
The response envelope has a separate hash in the manifest; its mutable metadata
is not the reproducibility pin. Reacquisition checks the source pin and version.

## Verified primary text

| Area | Requirement or observation | Source / qualification |
| --- | --- | --- |
| Model | Every agent uses `gemma-4-31b-it-qat-w4a16-ct`; LoRA is optional. | [Overview, model section](https://www.kaggle.com/competitions/gemma-4-developer-agent/overview/model-selection-budget-and-harness-rules) |
| Packaging | ZIP with `agent.yaml` at root. | [Overview, evaluation](https://www.kaggle.com/competitions/gemma-4-developer-agent/overview) |
| Loading | Restricted ADK configuration; relative `!include`; paths/symlinks cannot escape submission root. | Model section; full restrictions/parser not acquired. |
| Adapters | PEFT directories under `adapters/<name>/`, containing `adapter_config.json` and `adapter_model.safetensors`; `LlmAgent` selects `adapter: <name>`. | Model section; target modules and compatibility still unknown. |
| Tools | Harness tools or `agent_tool` subagents only. Shell, patch submission, budget status, read/edit/write and three graph-query tools are listed. Skills use `SKILL.md` frontmatter; script time debits the shared budget. | Model section; full signatures in primary page. |
| Score and time | Percentage of issues passing validation after patching; 12 hours across tasks, including sandbox setup, excluding patch validation. Optional per-task limits in `eval_config.yaml`. | Overview, evaluation. |
| Dates | Entry/team merger: 2026-11-25; final submission: 2026-12-02; optional paper: 2026-11-12. Each at 23:59 UTC. | Overview, timeline; subject to organizer updates. |

The [data description](https://www.kaggle.com/competitions/gemma-4-developer-agent/data)
reports 129 public development tasks and about 120 hidden tasks divided between
public/private scoring. Public tasks include reference `patch` and `test_patch`;
hidden grading separates those answers. Do not route these fields to agent inputs.
It describes offline wheels mounted at `/wheels/`, Python 3.13 sandbox build
specifications, frozen repository snapshots, graphs and embeddings. It identifies
`sample_submission/` and `HARNESS_README.md`, plus generated `submission.parquet`
with `id`/`prediction`. These are descriptions, not acquired file bytes. The data
viewer lists 524 files totaling 22.42 GB; no bulk download was attempted.

The [rules](https://www.kaggle.com/competitions/gemma-4-developer-agent/rules) state
one submission per day, at most two final selections, and teams of at most five.
They permit external data subject to accessibility, cost and licensing conditions;
hand-labeling/predicting validation or test records is prohibited. Private code
sharing outside teams is restricted. Public competition-code sharing requires
Kaggle forum/notebook sharing and a qualifying open-source license. Winner
licensing and reproducibility obligations also apply. Foundational rules take
precedence over conflicting specific rules.

**Preserve the rights ambiguity:** the summary labels data access/use Apache 2.0,
but specific rule 2.4.b restricts making Competition Data available to
nonparticipants; its definition includes provided prototype/executable code.
Do not treat the summary as blanket redistribution permission. This PR commits
only authored tooling, notes and acquisition metadata; no repository license is
selected. The owner must resolve public-sharing/license obligations before
participation or publishing a competition solution on Kaggle. No such publication
or agreement is performed here.

The [organizer welcome](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743007)
confirms starter/development/graph resources; it provides no additional executable
schema. Community comments were not treated as organizer requirements.

## Organizer notebook v2: verified code, not executed here

The [notebook](https://www.kaggle.com/code/ryanholbrook/getting-started-gemma-4-developer-agent)
UI displays Apache 2.0 for the notebook itself. We retain an acquisition manifest
instead of vendoring it or extending that license to its inputs.

- Cell `63cb4756` copies `sample_submission/`, then modifies
  `configs/sampling.yaml`: temperature 0.2, top_p 0.95, max_output_tokens 16384,
  thinking_budget 4096 and include_thoughts true; omits thinking_level.
  Thus notebook execution is not a byte-unchanged starter baseline. R0 must
  explicitly identify the chosen official/default variant and preserve the original.
- Cell `f0b1ab0d` uses model asset
  `google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2` (filesystem `other` lowercase),
  `gemma4` tool/reasoning parsers, context length 32768, tensor parallel 1/2/4,
  0.90 GPU memory utilization, LoRA enabled, max_loras 8, max_lora_rank 128,
  and a 1,200-second server startup allowance. These are notebook settings,
  **not independently verified competition-wide caps or upstream commit IDs**.
- It calls `validate_single_declared_model`, discovers adapters using
  `ALLOWED_ADAPTER_EXTENSIONS`, passes the manifest to `VllmServer`, then creates
  a registry with the declared/base aliases and `openai/` prefix. Exact discovery,
  target-module, alias, tokenizer/chat-template and adapter loading behavior
  requires implementation/config bytes we do not have.
- Cell `105c5b68` invokes `swegemma.evaluate.Evaluator` on two public tasks,
  with `EvalConfig`, `build_submission_limits()`, context caching/compaction,
  and `sandbox='subprocess'`. It reads `eval_config.yaml`; fallback values are
  300 seconds timeout, 100 tool calls, 60 minutes, and optional turns/LLM calls.
  The official overview instead describes persistent Docker skill execution.
  Preserve this notebook/deployment distinction; do not equate the two runtimes.
- Cell `d811048f` creates a ZIP and checks expanded size against
  `MAX_SUBMISSION_SIZE_BYTES` and suffixes against `ALLOWED_SUBMISSION_EXTENSIONS`.
  Its error string mentions 3 GiB, but the imported constant values and validator
  implementation are not acquired. These assertions do not prove complete validation.
- Metadata pins notebook image
  `gcr.io/kaggle-private-byod/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461`,
  names NvidiaL4, GPU enabled, internet disabled, and the metric wheelhouse input.
  Wheel versions are unavailable. The rendered run reports L4 x4. That is published
  organizer output, not execution by Backtrace or proof of hosted scoring.

## Missing contract and actionable access boundary

The data viewer explicitly says sign-in and agreement to competition rules are
required to view `HARNESS_README.md` (49.36 kB). The same gated dataset contains
`sample_submission/`. The owner controls agreement; no acceptance was attempted.

| Missing | Needed before using a competition-specific packaging/runtime path |
| --- | --- |
| Starter bytes and manifest | Authorized acquisition of `sample_submission/`, all includes and configuration; pin each file; preserve an unchanged local reference. |
| Harness guide and wheels | Authorized `HARNESS_README.md`, exact `swegemma`, `adk-submission`, `adk-eval-core` package versions/bytes; inspect official parser, validator/CLI and imported limits without assuming generic ADK behavior. |
| Model/tokenizer | Immutable checkpoint revision, tokenizer/chat template and configuration hashes, model terms; notebook asset version 2 alone does not establish these. No weights downloaded. |
| LoRA compatibility | Permitted rank/target modules, PEFT format details, base revision, quantization/training route and actual registration/load semantics. Notebook rank 128 is insufficient proof. |
| Hosted resources | Full dependency pins, CPU/GPU/RAM/storage/process/network restrictions, per-call timeout/turn limits, enforcement and aggregate timing semantics beyond the overview. |
| Submission mechanism | ZIP requirement is known; exact upload/runner contract and all rejection checks remain untested. No submission command is implemented. |
| Rights | Per-artifact redistribution/model/data conditions and public-code-sharing obligations require resolution before assets or a competition solution are published. |

`python3 tools/backtrace.py baseline` fails closed with these missing-artifact
instructions. The generic ZIP inspector uses conservative local limits; it does
not parse `agent.yaml`, import untrusted code, validate adapters or claim official
compliance. Acquisition of a public notebook is only partial official-artifact
acquisition, not a complete official baseline.
