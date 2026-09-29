# R0-clean-v2-one-public-task/T4-native-dtype

Continuation of Draft PR #5 after the [ChatGPT review](https://github.com/hynk-studio/backtrace/pull/5#pullrequestreview-5348487668)
and [Issue #1 checkpoint](https://github.com/hynk-studio/backtrace/issues/1#issuecomment-5884852735).
The original [pre-allocation STOP](r0-smoke-attempt.md) remains historical evidence.
No second PR or intermediate merge was required. The base remains
`d14a1542b7bb094f0e5bda7eb8482ddecafe8c57`; the reviewed head was
`2de98345c643651f6bdb38b425dd7f60ed2b9440`.

## Exact serving delta and frozen inputs

Only the serving cell's BF16 predicate changes:

```diff
- torch.cuda.is_bf16_supported()
+ torch.cuda.is_bf16_supported(including_emulation=False)
```

The original `bfloat16`/`auto` branches and all other serving settings remain.
The retained notebook v2 is unchanged. `tools/native_dtype.py` checks its pinned
hash before deriving the cell; the three synthetic regressions exercise native,
non-native and unavailable CUDA selections, exact source preservation, and drift
rejection. They inject capability results and are not GPU evidence.

| Private source | Bytes | SHA-256 |
| --- | ---: | --- |
| Original serving cell | 1,654 | `b125ed5ae91d19df1b3c2a3932bed1c5d901f97fcedafcce7f917e71cd59289d` |
| Native-BF16 derivative | 1,679 | `e09680a61a8bfb7a185a231bc1bd79a9d89284d6db42d6e67f6c050ebaec33ac` |
| Unified serving diff | 473 | `96c81692617fc858b6189161360f8f088759e571cf33b7e28c151f06487b1ec2` |
| Actual GPU script, including request timestamp | 26,410 | `c8f97c6434635f04677c823da8bec19d8605a70630050cbc7504e9d110aa9595` |

The full script and exact diff are retained privately under
`.local/smoke/native-dtype/`. They embed organizer source and are not vendored.
The wrapper implements the already-reviewed public-input separation, finite
process/session limits, task-only dependencies, observation and cleanup. It uses
`VllmServer.start`, `create_model_registry`, and `run_agent_sandbox`; it never calls
the full Evaluator. No framework, model metadata, weights, Torch or vLLM patch was added.

- **Task:** `fastapi_11194`; selection and metadata tree correspondence remain as
  recorded in the original attempt. No replacement task or reference outcome was inspected.
- **Model:** `google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2`.
- **Candidate:** 6,230 bytes, SHA-256
  `2e24495826cb971053439a00d9ad8350471fc0efffa41a54b82082feedaa7358`.
- **Five-field input:** 810 bytes, SHA-256
  `6ed92f4e646c17728aa8b9ca433a032d61b6b06827eec463a02c00f331c25d60`.
- **Budgets:** one minute, ten tool calls, fifty turns, sixty seconds per command.
  Prompts, sampling, caching, compaction, AgentTool wiring and no-adapter selections
  are unchanged. There is no extra warm-up model request or automatic rerun.

The acquired vLLM 0.19.1 source selects FP16 for `auto` with an SM75 platform and
BF16 Gemma4 configuration. A local execution of the actual selection functions
confirmed this with **injected** capability and dtype boundaries, for both
`gemma4` and `gemma4_text`. That does not establish observed CUDA resolution or
memory fit. Actual requested/resolved dtype must be reported separately below.

## Affordable prerequisites actually executed

Existing signed-in notebook access supplied the account API; no new credential,
OAuth grant or terms acceptance was needed. A clean UID 65534 child with no
supplementary groups, `no_new_privs`, an empty capability bounding set, and an
allowlisted environment could not read the root canary, the control parent's
`/proc/.../environ`, or use the account API. The GPU driver repeats these checks.
Root control credentials never enter the model/agent environment. No full
competition mount, answer record, gold patch, test patch, test lists or secret
bundle is present in the agent-readable inputs. Model/task processes use the
same restricted UID; a root supervisor kills and checks that UID, including
orphaned children. This is a tested credential/filesystem boundary, not a claim
of a complete kernel security sandbox. `unshare` was denied and Landlock returned
ENOSYS in the inspected CPU environment; neither was reported as active isolation.

The original snapshot's only branch reaches its pinned base tree through 6,065
commits; `git fsck --full --no-reflogs --unreachable` returned no unreachable
objects. No historical commit messages or reference-solution content were read
for task selection. This check is not an exhaustive audit of source history.

A private CPU-only input run produced exactly the selected snapshot, graph,
embedding, two dependency wheels, candidate and five-field task JSON, plus a
hash receipt. It completed in **36.3 seconds** (acquisition code: **26.897 seconds**).
No dataset license was selected; the outputs remain a private notebook input.
The selected embedding is 4,158,644 bytes, SHA-256
`46fb70dc9b0e8370136e7da78be77b04ff9f117af6fd67df0b0cc908a00bcef9`;
`numpy.load(..., allow_pickle=False)` found 3,255 float32 arrays of shape 256.

The exact organizer image was independently run on CPU, completing in **18.1
seconds**. It provides Python 3.12.13, Torch 2.10.0+cu128, FastAPI 0.136.1,
Starlette 0.52.1, Pydantic 2.12.3 and pydantic-core 2.41.4. CUDA was unavailable
on that CPU allocation; this was not a GPU compatibility test. Wheelhouse v25
contains the required 41 Linux wheels. The five original harness pins remain
unchanged, with vLLM 0.19.1 and the image's Torch 2.10.0+cu128.
Both the CPU image-check and completed GPU pages link to
`gcr.io/kaggle-gpu-images/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461`.
Their generic "Latest Container Image" label does not change the observed digest,
which matches the organizer's recorded `kaggle-private-byod` image digest.

The selected project's Starlette constraint excludes the image's 0.52.1. Official
`SubprocessManager` deliberately skips editable-package and test-dependency
installation and inherits parent packages. A **task-only** venv therefore installs
Starlette 0.48.0 and pdm-backend 2.4.9 from the selected official wheels. The
server keeps the original image plus notebook wheelhouse installation. No
serving dependency was silently replaced. Wheel hashes are in the source manifest.

CPU qualification caught two authored-driver preparation errors before allocation:
`ensurepip` failure (version 1, 88.2 seconds) and a closed-stream error during
harness import after the authentication check (version 2, 105.2 seconds).
The task venv now uses the existing image pip; authentication is checked in a
separate child and stdin is explicit. **Version 3 passed in 138.5 seconds**:
setup/check body **130.977 seconds**, official sandbox dependency inheritance
confirmed, no worker survivors, temporary workspace removed. The official
sandbox's own fallback without ensurepip ran unchanged. These are CPU preparation
runs, not additional model attempts. Their provider timeout was 420 seconds;
the template's printed 1680-second value describes the intended GPU envelope.

An independent provider-expiry test ran a private CPU script that sleeps for
180 seconds, pushed with `timeout='60'`. Kaggle canceled version 1 after **72.0
seconds**, explicitly reporting **timeout exceeded**. The sleep did not finish
and no manual stop caused that cancellation. The GPU request therefore uses
`timeout='1680'`, with useful work capped at request + 1620 seconds and setup at
request + 300 seconds (including request-to-process delay). The 120-second reserve
against the owner's 1800-second maximum accounts conservatively for provider
teardown; CPU timing does not prove an exact GPU expiry latency. Actual GPU
termination still requires independent provider readback. A durable request
marker prevents a repeated launch from the control session.

Immediately before the request, Kaggle showed **00:00 / 30 GPU hours** and offered
**GPU T4 x2**. [Kaggle's primary metadata documentation](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels_metadata.md)
identifies `NvidiaTeslaT4` as that two-device option. The model request is private,
uses that exact machine shape, disables internet, and mounts only model v2,
wheelhouse v25 and selected-input notebook version 1. No paid fallback exists.

## Observed single attempt

Request accepted at **2026-09-29 07:50:54.622955 UTC**. Private run ID **353810920**,
version 1, [owner-only run](https://www.kaggle.com/code/hynk1240/backtrace-r0-t4-native-dtype).
The request is `api.kernels_push(directory, timeout='1680', acc='NvidiaTeslaT4')`.

**STARTUP FAILED; the one authorized GPU attempt is consumed. No rerun.**
The provider reports version 1 as **ERROR**, **649.6 seconds**, T4 x2. Actual
inventory was two Tesla T4s, 15,360 MiB each, driver 580.159.04. The worker's
native BF16 predicate returned **false**, requesting **`auto`**. The actual vLLM
0.19.1 engine log records **`dtype=torch.float16`** and the exact version-2 model
and tokenizer paths. This is observed GPU resolution, separate from the injected
source check above.

Weights loaded: TP0 reported **90.96 seconds** for weights and **10.46 GiB /
92.432 seconds** for model loading. Both workers selected `TRITON_ATTN`. During
CUDA graph profiling, both workers emitted:

```text
Failed: Cuda error /workspace/csrc/custom_all_reduce.cuh:455 'invalid argument'
```

Worker 1 died; engine initialization failed while determining available memory.
The official wrapper raised `ServerStartupError`. This identifies the failing
operation, not its ultimate cause. There was **no observed OOM**, but successful
weight loading does not establish full runtime memory fit. Peak sampled usage
was **12,329 MiB per GPU** (two-second sampling). No custom-all-reduce flag,
compilation flag, parser, model metadata, weight or package was changed to retry.

| Boundary | Observed time |
| --- | --- |
| Request → root driver start | 13.199 s |
| Dependency setup and isolation → ready | 95.682 s from root start |
| All model-byte hashes checked; setup complete | 262.098 s from root start / **275.297 s from request**, inside 300 s |
| Official `server.start()` entered | 288.239 s from root start / **301.443 s from request**; worker imports are startup overhead |
| Official start → `ServerStartupError` | **350.524 s**; startup including worker initialization approximately **376.67 s**, below 1,200 s |
| Server stop return → root cleanup complete | 4.221 s |
| Root driver, through cleanup | **642.991 s** |
| Request → cleanup complete | **656.190 s** |
| Provider runtime | **649.6 s**; its timer is distinct from the request/root timers |
| Request → independent terminal API readback | **820.938 s**, below 1,800 s |

The provider's exact hardware-allocation start/end timestamps are not exposed.
649.6 seconds × two GPUs is approximately **0.361 aggregate GPU-hours**; using
the wider request-to-terminal-observation interval bounds this at **0.4561
aggregate GPU-hours**. Neither is a finer-grained account-meter receipt. Kaggle's
quota display changed from **00:00 / 30 hrs** to **00:10 / 30 hrs** and stayed
there after termination. Paid spend: **$0**. Useful work ended before both the
driver's request + 1620 deadline and the owner's request + 1740 ceiling.

`server.stop()` returned, the root supervisor observed **zero UID-65534 worker
survivors**, reaped children and removed the temporary workspace. vLLM emitted a
shutdown warning about three shared-memory objects; it does not override the
separate process/provider checks. The independent account API at
**2026-09-29 08:04:35.560896 UTC** returned `{"status":"ERROR","failureMessage":null}`.
The provider UI shows the completed failure, not a running GPU session. After
receipt retrieval the separate CPU control draft was explicitly stopped and
read back **off**, accelerator **None**; the refreshed Active Events badge was
empty. The temporary local keep-awake lease was also stopped and reaped.

| Verification stage | This continuation's result |
| --- | --- |
| Local tooling; actual-candidate CPU/schema checks | **PASS**, commands below; historical compiler probe not rerun |
| Exact model/input/environment acquisition | **PASS**: mounted v2 bytes, selected inputs and all 41 wheel hashes recorded privately; no public assets |
| GPU isolation and real official sandbox dependency check | **PASS** for the concrete credential/file checks and dependency command above; no task tool invocation |
| Model weights/dtype | **LOADED / FP16 observed**; not a healthy server |
| Model server health | **FAILED during startup**; no health or `/v1/models` success |
| Actual served identity, alias translation, request parameters, thinking-budget enforcement | **NOT RUN**; initialization names the pinned model, but no serving response or wire request exists |
| Returned model request; selected task; agent tools | **NOT RUN**; zero task executions and no returned model request |
| Patch | **NOT GENERATED**; no patch file/hash, distinct from an empty patch |
| Separate public-test verification | **NOT RUN**; no agent result and evaluator-only inputs were not mounted |
| Process / GPU session termination | **CONFIRMED** by supervisor cleanup and independent terminal provider state |
| Competition submission, acceptance, hosted scoring, training | **NOT RUN** |

The actual private version retains `execution.log` (30,104 bytes),
`server-error.log` (24,200 bytes), `model-files.json` (1,150 bytes),
`wheel-files.json` (7,413 bytes), and its main log (5,685 bytes). SHA-256 values and
source locations are recorded in the manifest. These were retrieved through the
account API into the CPU control session before it stopped; originals remain
private in the completed GPU version. No `wire.jsonl`, `task-result.json` or patch
was produced. Browser file download did not complete, so raw logs are **not
claimed as local workstation copies**. Only authored reports, hashes and code
are published. No inference/task success or research benefit follows from this run.

## Commands and local verification

Executed again in this continuation, from `/Users/hynk/code/backtrace`:

```sh
python3 -m unittest discover -s tests -p test_native_dtype.py -v
python3 -m unittest discover -s tests -v
python3 tools/backtrace.py preflight
python3 tools/backtrace.py verify-artifacts .local/official
.local/cpu-checks/bin/python tools/official_check.py .local/official --candidate .local/r0-clean/build-a.zip
python3 .local/smoke/native-dtype/check-auto-dtype.py
env -i PATH=/usr/bin:/bin /usr/bin/git --git-dir=.local/smoke/preallocation/snapshot-git fsck --full --no-reflogs --unreachable
git diff --check
git diff main...HEAD --check
```

Results: three focused tests and **49 total tests PASS** on local Python 3.9.6;
preflight READY within its documented scope; all **16 existing artifact pins
PASS**; the actual candidate's official CPU/schema, exact-delta and membership
checks PASS; source dtype check PASS with the explicitly injected boundaries;
Git object and whitespace checks PASS. No archive was rebuilt. SHA-256/size checks
of both existing ZIP copies and the five-field input matched the frozen identities.
The earlier compiler/tool-binding milestone was not rerun or reclassified.
These are this continuation's executions, separate from historical/reviewer tests.

Private preparation commands (none allocate a GPU locally):

```sh
PYTHONPATH=. .local/cpu-checks/bin/python .local/smoke/native-dtype/build_launcher.py
python3 .local/smoke/native-dtype/build_gpu_launcher.py
```

The local builder syntax-checks the materialized driver and preserves the exact
native-only serving-cell delta. The generated private launcher notebook was
imported through Kaggle's File → Import Notebook and executed once. Account API
calls used the already authorized CPU control session; no CLI auth or token
export was used for this allocation. Exact executed script identities are above
and in the source manifest. The control session's read-only follow-ups used
`api.kernels_status('hynk1240/backtrace-r0-t4-native-dtype')` and
`api.kernels_output(..., file_pattern=..., quiet=True)` with a 25-second retrieval
alarm, retaining only private operational receipts. No second push was made.

**One recommended next action:** ChatGPT should review the retained
custom-all-reduce startup failure and decide whether a separately authorized
serving deviation is warranted before any further GPU attempt.
