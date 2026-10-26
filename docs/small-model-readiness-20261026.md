# E2B/E4B tokenizer, loading and bounded-input preparation

Date: 2026-10-26. Refs [BT-001](https://github.com/hynk-studio/backtrace/issues/1).
Stacked on Draft #31 at `764a30465d01fba994a64e3d592c6e45a9b37711`.

This implements the next free A1 preparation step. Both official tokenizers
encode every qualified development prompt without truncation. A tiny random CPU
checkpoint probe exposed and corrected a full-wrapper to text-model loading
mismatch. The 36-request smoke and 288-request screening inputs are prepared;
**pretrained inference, GPU qualification, training and Augnes transfer are NOT
RUN**. A1 remains partial. No earlier paid permit is reused.

## Pinned identities and actual checks

The [runtime lock](small-model-runtime-lock-v1.json) records immutable revisions,
source URLs, exact sizes and SHA-256 hashes for seven metadata/tokenizer files
per model. A bounded HTTP Range request acquires only each safetensors header;
the tool requires HTTP 206 and the exact Content-Range before reading bytes.
No pretrained tensor values were downloaded. Full weight digests and sizes are
publisher metadata, not locally verified full-file digests.

| Candidate | Official repository | Immutable revision | Text parameters from meta-device construction | BF16 text parameter bytes, lower bound |
| --- | --- | --- | ---: | ---: |
| E2B | google/gemma-4-E2B-it | `3e22461f65e89153144f8adb70e3b8c2cc9845a7` | 4,628,569,344 | 9,257,138,688 |
| E4B | google/gemma-4-E4B-it | `ee0ef6023621cff504d758262d4e04895a5af4a2` | 7,463,013,376 | 14,926,026,752 |

These are text-model parameter-storage floors, excluding KV cache, activations,
loading peaks and allocator overhead. They are not measured VRAM. E4B's floor
alone exceeds the owner's 12 GiB deployment target, so BF16 all-GPU deployment
there is excluded by this bound. Quantization/offload quality and performance
remain separate untested choices; neither is silently enabled here. E2B fitting
its parameter floor also does not establish usable context or headroom.

The observed CPU environment is CPython 3.12.14 / Linux x86_64, Transformers
5.20.2, PyTorch 2.13.0+cpu, tokenizers 0.23.3, huggingface_hub 2.3.0, Jinja2 3.1.6
and accelerate 1.15.0. All 37 wheels have exact package versions and hashes in
the lock and [CPU requirements](small-model-cpu-requirements.txt). A fresh venv
was installed offline from 247,701,638 bytes of verified wheels; pip check passed.
The [CUDA candidate](small-model-gpu-requirements.txt) pins 56 resolved packages,
including PyTorch 2.13.0+cu126. Its status is RESOLVED_NOT_INSTALLED_OR_EXECUTED.
This is an inference candidate, not a qualified training/adapter environment.

## Loading failure found before pretrained execution

The pinned full checkpoint uses `model.language_model.*` text tensor names.
The initial tiny random full-wrapper checkpoint loaded through
`Gemma4ForCausalLM.from_pretrained` without a mapping reported missing and
unexpected text weights and initialized new weights. Treating that load as
success would invalidate subsequent performance evidence. The first failed
probe and its log are retained locally, separately from corrected results.

An explicit mapping from `^model\.language_model\.` to `model.` fixes this
observed path in Transformers 5.20.2. Corrected probes preserve E2B's 35-layer /
20-shared-KV-layer and E4B's 42-layer / 18-shared-KV-layer layouts while shrinking
tensor dimensions. Each saves a random full-wrapper checkpoint, reloads the
text model, rejects every missing/unexpected/mismatched key, compares logits
exactly (maximum difference 0), and generates two tokens on CPU. No gradients or
pretrained tensors are involved. This does **not** satisfy A2's actual pretrained
update or adapter save/reload gate.

Separately, official tensor-header names, BF16 dtypes and shapes match the
meta-constructed text models after mapping. Tied embedding/head storage is
handled explicitly. Only the known non-text tower prefixes and exact documented
redundant shared-KV keys are exempted; unknown components or missing/wrong text
weights fail. Header checks do not verify tensor values or actual GPU loading.

## Tokenization evidence

The original teacher/generator/scorers, temporal and baseline prompt sources
remain unchanged. `rebuild-packets` reconstructs the exact previously qualified
input bytes from development agent views without solving cases or reading
labels. It checks all original source hashes, manifest identity, packet hashes,
byte counts and record counts against the prior committed CPU receipt. It does
not claim to rerun that earlier full teacher qualification.

Each of the four packets contains 1,440 inputs: 160 episodes from eight existing
development families, with nine static/temporal views per episode. Across both
models there are **11,520 tokenization assignments**, not 11,520 independent
examples or observed inference calls. Both actual tokenizers give these counts:

| Packet | Minimum | Median | p95 | Maximum | Total input tokens per model |
| --- | ---: | ---: | ---: | ---: | ---: |
| B0 JSON | 693 | 1,021 | 1,250 | 1,288 | 1,469,086 |
| B1 JSON | 792 | 1,120 | 1,349 | 1,387 | 1,611,646 |
| B0 controlled English | 781 | 1,119 | 1,393 | 1,462 | 1,649,902 |
| B1 controlled English | 880 | 1,218 | 1,492 | 1,561 | 1,792,462 |

Overflow is zero at the proposed 12,288 input / 4,096 new-token ceilings. The
real configuration context ceiling is 131,072; the tokenizer's huge sentinel
value is not used as the context limit. Counting reads BatchEncoding input_ids,
not the number of dictionary keys. Template token IDs must match explicit text
encoding without added special tokens, contain exactly one leading BOS and an
unchanged native system role / model-generation prefix. No padding, truncation,
thinking prefix, label access or fallback prompt transformation is accepted.

This first regime is greedy, no-thinking, batch one, no tools and no retries.
It is a controlled regime, **not a model capability ceiling** or the vendor's
recommended sampling recipe. A later thinking/sampling regime must be specified
before confirmatory evaluation and matched across relevant controls. Output
transport is specified to retain raw IDs and text, remove only one true terminal
1 or 106, and mark tool boundary 50 or thought/tool output invalid. JSON repair
and selective answer extraction are prohibited. That collector still needs
implementation and connected qualification.

## Bounded development scopes

Selection is fixed before model output: SHA-ordered development families,
variant zero, all nine views of each episode, matched B0/B1 JSON inputs. IDs and
selection metadata remain outside model messages. The full controlled-English
grid was tokenized but is not part of these initial JSON scopes.

| Scope | Families / episodes | Requests per model | Both models | Input tokens per model | Maximum output tokens per model |
| --- | ---: | ---: | ---: | ---: | ---: |
| Smoke | 1 / 1 | 18 | 36 | 19,301 | 73,728 |
| Screening | 8 / 8 | 144 | 288 | 154,468 | 589,824 |

Smoke is for implementation and throughput; screening is a descriptive pilot
with one episode per family, not powered confirmation. Assigned failures and
missing responses stay visible in the denominator, with no replacement cases or
automatic retries. Failure to execute a model is not evidence it answered
incorrectly; report coverage and conditional task metrics separately.

Only the smoke includes a conditional cost proposal: one GPU, models sequential,
at least 24 GiB as an unmeasured candidate, allocation-inclusive 3,000 seconds,
compute at most USD 0.90, other charges at most USD 0.10, all charges at most
USD 1.00 and hourly compute at most USD 1.00. A fresh quote including minimum
billing and fees must fit all caps, and fresh balance must leave USD 0.50 reserve.
These are proposed ceilings, **not provider prices, current balance, measured
completion time or launch authorization**. Screening has no paid budget approval.
No existing paid controller, permit, workflow or watcher is changed.

Before paid execution: implement and CPU-qualify the bounded inference collector,
input-only OS isolation and evaluator connection (including failure/deadline
paths); install/check the CUDA environment; bind actual weight verification and
loading diagnostics; then prepare a concrete fresh resource/price/balance
proposal. Actual GPU loading, throughput and peak memory are measurements of
that separately authorized bounded run, not prerequisites claimed complete here.

## Reproduction and validation

Use fresh `.local` output paths. Source acquisition is public metadata/tokenizer
traffic only; the last two commands use the qualified CPU venv with
HF_HUB_OFFLINE=1 and TOKENIZERS_PARALLELISM=false.

```sh
python3 -m unittest discover -s tests -v
python3 tools/backtrace.py preflight
python3 -m tools.small_model_readiness acquire .local/model-sources
python3 -m tools.small_model_readiness rebuild-packets .local/packets
.local/runtime/bin/python -m tools.small_model_readiness random-layout-probe .local/model-sources .local/random-layout
.local/runtime/bin/python -m tools.small_model_readiness tokenize .local/model-sources .local/packets .local/tokenization.json
python3 -m tools.small_model_readiness prepare-scope .local/packets .local/tokenization.json .local/smoke --scope smoke
python3 -m tools.small_model_readiness prepare-scope .local/packets .local/tokenization.json .local/screening --scope screening
```

The [native CPU workflow](../.github/workflows/small-model-readiness-cpu.yml)
creates the exact venv, hash-checks wheel acquisition, installs offline and runs
the full Linux suite, preflight, metadata acquisition, byte-exact reconstruction,
both random probes, all tokenization assignments and both scopes. Its artifact
contains summaries, hashes and token IDs' digests, not weights or raw prompts.
Native run [40301835535](https://github.com/hynk-studio/backtrace/actions/runs/40301835535),
attempt 1, passed at source `47f89819e89743b73363fa208035f1c781891221`, tree
`1dcd2678648a0ff8cd012f6afabdc07d3f833035`: all **575 tests**, no failures,
errors or skips, followed by every preparation step above. Artifact 12640353622
has verified SHA-256
`95b75bd93e74eed060711cb81123cf40c14f270d36452c7fd98b5bda86f1b276`.
All 12 archive members and 15 qualified source hashes were checked. Actual
tokenization cases/summaries, both bounded scopes, acquisition and preflight
were byte-identical locally and on native Linux; random loading results matched.
The [verified CPU receipt](small-model-readiness-cpu-20261026.json) binds these
results and preserves earlier local failures. Its follow-up commit changes
documentation only; it does not claim a new source execution.

Local focused tests: 21 passed. The local full-suite attempt exited 1 without a
final unittest summary; its retained log ends during the existing startup-guard
tests and shows failures/errors in pip-fixture and startup/procfs checks. The
terminal cause is not established from that log. It is
INCOMPLETE/FAILED, not a pass or an asserted complete 575-test result. Preflight,
actual offline installation, corrected random probes and full tokenization
passed independently. Native qualification above remains a separate result.

## Primary-source provenance and limits

Read 2026-10-26 UTC. Acquired immutable model files and safetensors headers have
exact hashes/URLs in the lock; general documentation was read, not byte-archived:

- [Official E2B card](https://huggingface.co/google/gemma-4-E2B-it) and
  [E4B card](https://huggingface.co/google/gemma-4-E4B-it): model identities,
  native template and configurable thinking; not our capability evidence.
- [Transformers Gemma 4 documentation](https://huggingface.co/docs/transformers/en/model_doc/gemma4)
  and the installed 5.20.2 code: text-model class and loading implementation.
- [Google Hugging Face inference guide](https://ai.google.dev/gemma/docs/core/huggingface_inference):
  supported usage; the concrete mapping result above is our observed probe.
- [PyTorch installation versions](https://pytorch.org/get-started/previous-versions/),
  official CPU/CUDA wheel indexes and PyPI metadata: dependency identities.
  CPU wheel hashes were verified from actual bytes; the CUDA set is resolver
  evidence only.

No pretrained task score, training improvement, uncertainty interval, deployment
fit, broader E2 missing-cause discovery or real Augnes transfer is established.
Kaggle participation remains optional and undecided.
