# R0-clean-v2-one-public-task/T4x2 — pre-allocation STOP

2026-09-29 UTC. The owner explicitly authorized one private free-quota attempt.
Read the complete [merge checkpoint](https://github.com/hynk-studio/backtrace/issues/1#issuecomment-5883903274),
[PR #4 review](https://github.com/hynk-studio/backtrace/pull/4#pullrequestreview-5347769851),
working agreement and [frozen recipe](r0-smoke.md). Verified a clean checkout,
correct origin, open Issue #1, merged PR #4 and no open PRs. Fast-forwarded main
and branched **bt-001-r0-smoke** from
`d14a1542b7bb094f0e5bda7eb8482ddecafe8c57` (tree
`a5c552957e8e25c5f93966feed3fe5ebcd9d3868`). No merged branch changed.

## Decision and evidence boundary

**Do not allocate for the unchanged recipe.** Notebook v2 chooses BF16 using
`torch.cuda.is_bf16_supported()` with its default argument. PyTorch 2.10 defaults
to `including_emulation=True`, and its pre-Ampere path accepts successful BF16
tensor creation. NVIDIA identifies T4 as compute capability **7.5**. In the
actual acquired vLLM 0.19.1 wheel, `CudaPlatformBase.check_if_supports_dtype`
rejects BF16 below **8.0**; `gpu_worker.py` invokes that guard before distributed
initialization. Its model-config parser preserves an explicit `bfloat16` choice;
only `auto` takes the platform-compatible dtype fallback. This conflicts with
the notebook's emulation-inclusive selection.
Sources: [PyTorch 2.10 source](https://github.com/pytorch/pytorch/blob/v2.10.0/torch/cuda/__init__.py),
[documented signature](https://docs.pytorch.org/docs/2.10/generated/torch.cuda.is_bf16_supported.html),
[NVIDIA capability table](https://developer.nvidia.com/cuda/gpus), and the
[official wheelhouse v25](https://www.kaggle.com/datasets/metric/gemma-4-developer-agent-wheelhouse).
The earlier [PyTorch maintainer discussion](https://github.com/pytorch/pytorch/issues/118122)
also distinguishes emulated BF16 on Turing from compiled-kernel support.

This is a **source-based incompatibility inference**, not an observed T4 return
value or GPU failure. A local conditional reproduction evaluated the pinned
notebook's actual dtype expression and the acquired vLLM guard, with **injected**
SM75 capability and successful BF16 tensor allocation: dtype `bfloat16`, guard
`ValueError`. It made no GPU/model call. The actual Kaggle CPU environment
independently exposed the same emulation-inclusive PyTorch signature/source.
No claim is made that a CUDA tensor allocation or kernel executed on that CPU.

Do not confuse this with blanket Turing rejection: the acquired WNA16 and Marlin
implementations both declare minimum capability **75**. The v2 config specifies
symmetric INT4, group size **32**, `pack-quantized`/`compressed-tensors`,
`Gemma4ForConditionalGeneration`, and BF16 source dtype. Empirical memory fit,
the CUDA binary environment and a usable attention/kernel combination remain
unknown. No smaller context, dtype override or alternate checkpoint was tried.

## Frozen choice and private acquisitions

The rule selected **fastapi_11194**, repository **fastapi/fastapi**, metadata base
commit **a7f2dbe976bf72703376f0cd04487bfc4a849f83**, from **129 distinct IDs**.
Selection was pinned at **05:13:36 UTC**, before reference-solution/outcome
inspection. Conflicting duplicate records are rejected. The authored selector
reproduces the original selection and emits exactly `instance_id`, `repo`,
`base_commit`, `problem_statement`, `hints_text`; only the official optional
`hints_text` default may be empty when absent. Full metadata stays in a separate
local evaluator-only directory; no full dataset was mounted or uploaded.

| Retained artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Frozen R0-clean ZIP (unchanged) | 6,230 | `2e24495826cb971053439a00d9ad8350471fc0efffa41a54b82082feedaa7358` |
| Model v2 `config.json` | 18,711 | `b100d85e571c25b688e82919d819253063a1defb0e6cee3b9b1c1fbad99bd0c2` |
| vLLM 0.19.1 Linux wheel | 433,132,506 | `6b29fdc200966eda4d0cc4d10b8c338ec32620bb069ad3629d8a78e3b35fd3fa` |
| Public `tasks.jsonl` | 1,984,455 | `e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6` |
| Selected `fastapi_11194.tgz` | 214,241,984 | `21e42341f416904a0e464cac84f227ff8351bb652d522192212737e6dec663d1` |
| Selected base-commit graph JSON | 3,787,549 | `7ec16396393fadd398243098622c524f341778151c0455bdfec3ef7b0ff812df` |
| Derived five-field `agent-task.json` | 810 | `6ed92f4e646c17728aa8b9ca433a032d61b6b06827eec463a02c00f331c25d60` |

The model is still explicitly
**google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2**. Its viewer reports **23.3 GB**
and eight files. Only the small configuration was saved; weights, tokenizer,
chat template and generation configuration were **not acquired**. No model
asset was attached to a Kaggle session. The vLLM wheel records revision
`gb1388b1fb`, requires torch **2.10.0**, torchaudio **2.10.0**, torchvision
**0.25.0**, compressed-tensors **0.15.0.1**, and flashinfer packages **0.6.6**.
Wheelhouse v25 lists transformers **5.13.1**; those other Linux wheels were not
acquired/installed here. The five original harness/schema pins remain unchanged.

The snapshot has **2,941 entries / 226,851,181 expanded bytes**. Its rewritten
HEAD is `abd0ef6b5ef05f56d2b3e128ac16b25cd6a6c6ba`; the metadata commit is absent
from that object database. Read-only Git-object inspection found tree
`ce1ff0e44176b7bed89e62d497073e20e4e9b6e9`, exactly matching the upstream metadata
commit's tree from GitHub. This establishes tree identity, not a complete audit
of every historical object or future-answer isolation. No task checkout ran.

[Source manifest](source-manifest.json) records acquisition times, source URLs,
versions and member hashes. Third-party bytes, scripts and operational receipts
remain under ignored `.local/smoke/`. No competition asset, answer, credential,
candidate archive or license is published by this PR.

## Observed Kaggle controls and resource evidence

Existing signed-in browser access downloaded only the named files. Download
event waits timed out for the wheel despite a completed local download; hashes
were computed from retained bytes. Model JSON opened inline and was saved using
Chrome Save As. These were not new sign-in/rules gates. The CLI model-file listing
did require authentication; an uncompleted `auth login --no-launch-browser`
ended at EOF before browser authorization. No new credential or grant was made.

At approximately **05:12 UTC**, settings showed **00:00 / 30 GPU hours**, and the
accelerator selector offered **GPU T4 x2**. None remained selected. A finite
20-second CPU-only cell completed in **20.02 seconds**. The separate Kaggle
**Stop session** control returned the draft to **off**. A second finite CPU
metadata check completed in **4.296 seconds**, child exit **0**, under a sanitized
environment and **60-second** subprocess timeout; its temporary home was removed.
That CPU session was also stopped through Kaggle and observed **off**. No model,
task, tool body, server, input mount or saved/published notebook version ran.

Observed CPU metadata: Python **3.12.13**, Linux **6.12.90+**/glibc **2.35**,
torch/torchaudio **2.10.0+cpu**, torchvision **0.25.0+cpu**, transformers **5.0.0**,
google-adk **1.29.0**, litellm **1.82.4**; vLLM/triton absent, CUDA unavailable.
The draft displays original environment **2026-07-01**. This is **not the GPU
environment**, a reproduction of the organizer image, or an installed official
serving stack. Writable space was **20,940,599,296 bytes free** (~19.5 GiB).
Selected read-only closure and peak scratch needs are not fully established.

GPU allocation/startup/task/cleanup times: **not applicable; no GPU allocation**.
Aggregate GPU consumption **0 GPU-hours**, paid spend **$0**. CPU cell durations
above are observed; full CPU-session wall times were not instrumented. Final
reload again showed **00:00 / 30 GPU hours**; the Share dialog confirmed
**Private**, and the stopped draft has no inputs. The
manual session control worked; an unattended hard-expiry mechanism for a GPU
session was **not established or tested**. The owned local display-awake
lease was explicitly stopped and its process reaped.

## Commands and verification

Newly executed locally (all exit **0**, unless explicitly noted):

```sh
python3 -m unittest discover -s tests -v
python3 tools/backtrace.py preflight
python3 tools/backtrace.py verify-artifacts .local/official
python3 tools/select_smoke_task.py .local/smoke/evaluator-only/tasks.jsonl .local/smoke/agent-task.checked.json
cmp .local/smoke/agent-task.checked.json .local/smoke/agent-inputs/agent-task.json
shasum -a 256 .local/r0-clean/build-a.zip .local/r0-clean/build-b.zip
stat -f '%z %N' .local/r0-clean/build-a.zip
.local/cpu-checks/bin/python tools/official_check.py .local/official --candidate .local/r0-clean/build-a.zip
python3 .local/smoke/preallocation/check-dtype-branch.py
gh api repos/fastapi/fastapi/git/commits/a7f2dbe976bf72703376f0cd04487bfc4a849f83 --jq '{sha: .sha, tree: .tree.sha, parents: [.parents[].sha]}'
git --git-dir=.local/smoke/preallocation/snapshot-git cat-file -p abd0ef6b5ef05f56d2b3e128ac16b25cd6a6c6ba
git diff --check
git diff main...HEAD --check
```

Git-object commands ran with a sanitized environment against only privately
copied pack/index/ref bytes. Checking the original metadata commit in that
rewritten database exited **128**, as noted above. CLI `kaggle models instances
versions files google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2` and
`kaggle auth login --no-launch-browser` each exited **1**, for authentication
required and EOF respectively. These did not allocate or execute anything.

**46 tests PASS**, including five new authored synthetic selection regressions;
preflight READY; **16 existing pins PASS**; actual candidate CPU/schema/exact-delta
checks PASS. Existing compiler integration and pip checks were **NOT RERUN**.
The private metadata cell's script SHA-256 is
`6ab439a75427ae87aac0915951188733f285739f4dbac4f2f995603bc8663ca8`;
conditional source-reproduction script SHA-256 is
`0f1209ecab1111160f7070a54c02a018458607cb21e05aafda24100425090d96`.
Neither is the full proposed model/task execution script.

## Remaining stages and next decision

Acquisition is **partial**: selected embeddings/dependency closure and model
weights/tokenizer/template are missing. The actual GPU image/lock, full private
driver, agent OS/credential isolation and independent 1,800-second session expiry
are **NOT VERIFIED**; they were not completed after the dtype stop. No private
input dataset or model was uploaded/mounted. The agent's reference-field
exclusion is tested locally, not proven in a running Kaggle agent environment.

Server loading/health, actual served identity, returned inference, effective
request/thinking parameters, sandbox/tools, generated patch (including empty
patch), public-test verification, Kaggle submission acceptance and hosted scoring
are all **NOT RUN**. There is no patch hash or performance result to report.
The original candidate, prompts, sampling, budgets, AgentTool and no-adapter
choices remain byte-identical. The one model attempt has not started.

**One recommended next action:** review and authorize a named **T4-native-dtype**
serving deviation using native BF16 capability detection
(`including_emulation=False`) before resuming this same frozen task/envelope.
This proposal is not applied here and does not assert model fit or kernel
compatibility. No paid/hardware/checkpoint fallback is proposed by this PR.
