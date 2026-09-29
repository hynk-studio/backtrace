# R0-clean-v2-one-public-task/T4-native-no-custom-ar

This is the one additional attempt explicitly authorized after the
[PR #5 review](https://github.com/hynk-studio/backtrace/pull/5#pullrequestreview-5349920811)
and [Issue #1 checkpoint](https://github.com/hynk-studio/backtrace/issues/1#issuecomment-5886786192).
It continues reviewed head `6357b8e9525a786df166036f82f509dd715745a6` on
`bt-001-r0-smoke`, base `d14a1542b7bb094f0e5bda7eb8482ddecafe8c57`.
The [original pre-allocation STOP](r0-smoke-attempt.md) and
[first failed GPU attempt](r0-native-dtype.md) remain separate history.
Neither failure authorizes automatic configuration experiments or another run.

## Pre-allocation evidence and exact change

The previous private `execution.log`, `server-error.log` and main log were
retrieved into `.local/smoke/no-custom-ar/prior-originals/` this continuation.
Their hashes match the previous receipt. This is a new local acquisition; it
does not change the earlier report's statement that workstation download had
not completed then. The first error followed NCCL 2.27.5 initialization,
SM75 symmetric-memory rejection, weight loading, compilation and CUDA graph
profiling: `custom_all_reduce.cuh:455 'invalid argument'`. Subsequent worker death
and engine initialization errors do not identify the ultimate allocator/P2P cause.
There was no preceding observed OOM. No allocator or communication environment
variable was changed to infer or fix that cause.

The only new serving setting is the pinned wrapper's supported `extra_args`:

```diff
     tensor_parallel_size=tp_size,
+    extra_args=['--disable-custom-all-reduce'],
     startup_timeout=60 * 20,
```

The native-only BF16 predicate and `bfloat16`/`auto` branches remain unchanged.
The original notebook v2 is untouched. `tools/native_dtype.py` derives this
single-line change after checking source shape. The pinned adk-submission 0.2.11
`VllmServer.build_cmd()` appends `config.extra_args` to the actual launch argv;
`BaseInferenceServer.start()` uses that method. vLLM 0.19.1's argument parser
forwards the option to `ParallelConfig.disable_custom_all_reduce`. Its CUDA
communicator skips the custom-all-reduce constructor when that setting is true.
PyNccl is a separate communicator; symmetric-memory/FlashInfer routes and final
PyTorch fallback are separately conditional. The flag does not assert which
backend serves every collective. Source locations and acquired-byte hashes are
in [the manifest](source-manifest.json).

The focused CPU integration check uses the actual six-file candidate and real
pinned `VllmConfig`, adapter discovery and `VllmServer.build_cmd()`. It injects
T4 capability results only. The generated argv contains the flag **exactly once**;
removing it reproduces the previous command exactly, and every other config
field matches. No server or subprocess starts in this check; network/process
attempts are denied. Config retains `enable_lora=True`, max_loras 8, max rank 128.
For an empty adapter manifest this official wrapper omits LoRA command flags in
both old and new argv; this is unchanged wrapper behavior, not a new capability
change. The private driver asserts its actual command before starting once.

Private exact diffs and hashes are retained, not published as competition source:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| New serving cell | 1,727 | `aa88e606ccde951abc54e517ab5b1180e15df0d4a914b239c1332dad40054cd6` |
| Serving diff from native-BF16 cell | 294 | `f501fa685b822ce2c997f1ab2527014e80add1b0d3b07efb693990c0cbc3f388` |
| Driver before request timestamp | 33,461 | `c7eda43a043535eed064b8f347bf271b22eb235c539e44dfe1633c43f47f5189` |
| Driver diff from prior core driver | 18,325 | `7bd960ba30ebda67c4835813788763332d6ae1daa4492a5c474315251958bbef` |
| Actual timestamped execution script | 33,540 | `a96330d96b4485ce02b826a60396f23293465b40ae0e9971e00ce26a43177b7d` |

Outside the serving line and run name, driver changes are assertions against
previously recorded model/wheel hashes and observations of actual argv, device
capabilities, selected non-secret environment variables and effective server
configuration. No new model request or tool was added. The setup, EvalConfig,
agent phase, credential separation and cleanup implementation remain unchanged.
The two task-only dependency wheels remain separate from the serving environment.
The effective config readback occurs only if startup succeeds.

## Frozen inputs and allocation bounds

- Task **fastapi_11194**; five-field agent JSON **810 bytes**, SHA-256
  `6ed92f4e646c17728aa8b9ca433a032d61b6b06827eec463a02c00f331c25d60`.
- Candidate **6,230 bytes**, SHA-256
  `2e24495826cb971053439a00d9ad8350471fc0efffa41a54b82082feedaa7358`.
  Existing copies were checked; no rebuild, prompt, sampling, AgentTool, adapter,
  caching, compaction or budget change.
- Exact model **google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2**;
  TP=2, context=32768, requested dtype=`auto`, quantization unchanged.
- Same image digest `37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461`,
  wheelhouse v25, vLLM 0.19.1, Torch 2.10.0+cu128 and five harness pins.
- Reused private selected-input notebook version 1; its 1,778-byte receipt hash
  `b6517713cc1eaf5bf3d341f5979f72b5eb7482de87b588ceb2c090139c8c67e8`
  was reacquired before allocation and matched all seven input identities. No
  bulk data or reference-answer acquisition was performed. Actual mounted hashes
  are checked again before starting the model.

Before the request, Kaggle showed **00:10 / 30 free GPU hours**, offered T4 x2,
and reported the selected-input version COMPLETE and the prior GPU run ERROR.
The already-qualified provider timeout was reused: `timeout='1680'`, useful
work stops by request +1620 seconds, setup by +300, startup at most 1200 within
the remaining total. Owner maximum remains 1800 seconds, one server start,
one task at most, one aggregate GPU-hour, $0. Task limits remain one minute,
ten tool calls, fifty turns, sixty seconds per command. No eager/graph,
allocator/NCCL/P2P environment, package, LoRA, model or hardware workaround.

The retained prior request receipt is unchanged. The earlier nonpersistent CPU
session's on-session marker was absent after that session stopped; this control
session restores a clearly labeled consumed guard from the retained receipt.
It never overwrites a present old guard. A distinct new exclusive marker and a
workstation-persistent additional-attempt guard prevent this authorization being
reused. No request is repeated after an ambiguous response. Marker restoration
is not claimed to reproduce the original marker bytes.

## Execution result

Request accepted **2026-09-29 09:29:00.961682 UTC**, private version 1,
run ID **353835216**, [owner-only run](https://www.kaggle.com/code/hynk1240/backtrace-r0-t4-no-custom-ar).
**STARTUP FAILED; this additional authorization is consumed. No third run.**
The actual argv contains the new option once. vLLM's parsed non-default arguments
and engine initialization both record **`disable_custom_all_reduce=True`**,
**`dtype=torch.float16`**, TP 2, context 32768, compressed-tensors quantization
and `enforce_eager=False`. These are observed initialization values, not a healthy
`/server_info` response. Both actual GPUs report SM75 and native BF16 false;
requested dtype remains `auto`. The provider's image link resolves to the same
pinned digest above.

Communication initialization records **backend=nccl** on both ranks and
**NCCL 2.27.5** through `pynccl.py`. SymmMem reports SM75 unsupported. Exact
per-collective dispatch was not instrumented; the source-based fallback analysis
is not reported as observed use of every collective backend. The selected
non-secret environment readback retains `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`;
`PYTORCH_ALLOC_CONF`, the inspected NCCL/P2P/SHM/IB/debug overrides and VLLM
symmetric-memory/FlashInfer overrides were unset. No environment tweak was made.

Weights loaded in **85.29 seconds** (model load **86.878 seconds / 10.46 GiB**).
Both workers selected **TRITON_ATTN**. At **09:39:50 UTC**, both entered graph
memory profiling with the unchanged PIECEWISE=51/FULL=35 sizes. The first worker
exception at **09:40:01 UTC** reaches `kernel_unified_attention_2d` through
`profile_cudagraph_memory → _warmup_and_capture → _dummy_run → triton_attn`:

```text
triton.runtime.errors.OutOfResources: out of resource: shared memory,
Required: 98304, Hardware limit: 65536.
```

This is a concrete Triton kernel shared-memory resource failure, distinct from a
reported global VRAM OOM and from the prior custom-all-reduce invalid argument.
The previous error did not recur, but **graph profiling did not complete**;
there is no claim that initialization passed that entire stage or that the
original error's ultimate cause has been identified. Peak sampled GPU memory
was **12,291 MiB per device** (two-second sampling), not proof of runtime fit.
No block-size, num_stages, graph, context or backend workaround was attempted.

The child error was in the retained private server log while the live provider
page exposed only the root driver's progress. The official wrapper continued
polling its still-running API process until its configured **1200-second health
wait** expired. `start()` surfaced `ServerStartupError` after **1210.852 seconds**,
including the wrapper's stop/kill wait; it did not surface the earlier worker
exception promptly. Thus the observed `start()` wall time exceeds 1200 by
10.852 seconds; do not report it as an exact <=1200-second call. The official
source checks API-process exit and health, not worker log errors, and `stop()`
has a ten-second terminate wait before kill. No extra useful work, start or task
occurred during that delay. Total and cleanup limits remained within the owner
maximum. This observation warrants review before any future allocation; it is
not silently repaired in this slice.

| Boundary | Observed duration |
| --- | ---: |
| Request → root driver start | 5.731 s |
| Dependencies/isolation ready, from root start | 96.693 s |
| Model hashes complete, from root start / request | 277.748 s / **283.479 s**, within setup cap |
| Request → official server start | 311.154 s; worker imports are startup overhead |
| Official `start()` → failure including its stop wait | **1210.852 s** |
| Explicit stop return → root cleanup complete | **11.284 s** |
| Root driver through cleanup | **1527.560 s** |
| Request → cleanup complete | **1533.291 s**, before useful deadline 1620 |
| Provider runtime | **1536.5 s**, a separate timer |
| Request → independent terminal API observation | **1564.903 s**, below 1800 |

The exact hardware allocation timestamps are not exposed. Provider runtime ×2
is **0.85361 aggregate GPU-hours**; the wider request-to-terminal-observation
interval bounds this at **0.86940 GPU-hours**, below the additional attempt's
one-hour cap. These are interval calculations, not a precise account meter.
Kaggle's quota display moved **00:10 → 00:36 / 30 hrs**. Paid spend **$0**.
The provider timeout 1680 did not need to fire; independent termination was
observed earlier. Its historical CPU expiry qualification remains separate.

`server.stop()` returned; the root supervisor killed/reaped remaining children,
reported **zero UID-65534 survivors**, and removed its temporary workspace.
The account API at **2026-09-29 09:55:05.864716 UTC** returned terminal **ERROR**;
the provider UI records the completed 1536.5-second failure. The separate CPU
control session was explicitly stopped and read back **off / accelerator None**.
Both consumed guards were copied as exact private bytes before stopping it.

| Verification stage | This attempt |
| --- | --- |
| Local tooling / actual-candidate official CPU checks | **PASS**, commands below |
| Actual mounted model, inputs and wheel hashes | **PASS**, unchanged from retained pins |
| Real sandbox dependency command / credential boundary | **PASS**; this was preparation, not an agent tool call |
| Actual device, resolved dtype, applied serving flag | **OBSERVED**: T4/SM75, FP16, custom all-reduce disabled |
| Weight loading | **LOADED**, not full model/runtime readiness |
| Graph profiling / server health | **FAILED**, Triton shared-memory error followed by wrapper health-wait expiry |
| Served-model endpoint identity | **NOT RUN**; initialization names model v2, no successful `/v1/models` readback |
| Model alias/request/thinking parameters or enforcement | **NOT RUN**; no wire request or returned completion |
| Frozen task / agent tools | **NOT RUN**, zero task starts |
| Patch | **NOT GENERATED**; no patch file/hash, distinct from an empty patch |
| Separate public-test verification | **NOT RUN**; no agent result and no evaluator-only input mount |
| Process / GPU session termination | **CONFIRMED** by supervisor and independent provider state |
| Competition submission/acceptance, hosted scoring, training | **NOT RUN** |

Operational originals, exact source diffs, both guards, raw server error and
input/model/wheel receipts are private in `.local/smoke/no-custom-ar/` and the
completed private Kaggle version. No `wire.jsonl`, task-result JSON or patch was
produced. No performance or research-hypothesis conclusion follows from this
startup attempt.

## Local commands and source boundaries

Executed from `/Users/hynk/code/backtrace` in this continuation:

```sh
python3 -m unittest discover -s tests -p test_native_dtype.py -v
python3 -m unittest discover -s tests -v
python3 tools/backtrace.py preflight
python3 tools/backtrace.py verify-artifacts .local/official
.local/cpu-checks/bin/python tools/official_check.py .local/official --candidate .local/r0-clean/build-a.zip
env -i PATH=/usr/bin:/bin LANG=en_US.UTF-8 .local/cpu-checks/bin/python -I -B tests/official_server_command.py
python3 .local/smoke/no-custom-ar/prepare_driver.py
python3 .local/smoke/no-custom-ar/build_gpu_launcher.py
git diff --check
git diff main...HEAD --check
```

**51 local tests PASS** (Python 3.9.6), including five focused source-selection
regressions. **One opt-in real-wrapper CPU test PASS** in the pinned isolated
Python 3.12 environment. Preflight READY, all **16 original artifact pins PASS**,
and actual-candidate official CPU/schema, membership and exact-delta checks PASS.
Injected capability results in the command test are separate from GPU observations.
The historical compiler/tool-binding probe was **NOT RERUN**. These are Codex's
new executions, not ChatGPT's independent review results.

The first local driver preparation caught an authored receipt-shape mismatch
(list versus object) before writing or allocating; the corrected builder produced
the pinned script above. A separate AST/source comparison verified unchanged
setup, EvalConfig, environment, input pins, agent phase and isolation/cleanup.
The private serving bytes match the helper exercised by the real-wrapper test.

The prepared launcher was entered in the existing private CPU notebook cell and
executed **once**. Its only GPU request was:

```python
api.kernels_push(directory, timeout='1680', acc='NvidiaTeslaT4')
```

The actual pinned `VllmServer` command uses the environment's Python interpreter
with `-m vllm.entrypoints.openai.api_server`, explicit version-2 model path,
localhost:8000, context 32768, dtype auto, memory fraction 0.9, TP 2, auto tool
choice, gemma4 tool/reasoning parsers, and the one new flag. The full argv is in
private command receipts. Status and output reads use the owner-authorized
`api.kernels_status(...)` and `api.kernels_output(..., file_pattern=..., quiet=True)`
with finite retrieval alarms. No token/cookie or credential value was exported.
Only authored code, hashes and redacted observations enter this public PR.

**One recommended next action:** ChatGPT should review this Triton shared-memory
failure and delayed wrapper error reporting before deciding whether any further
GPU attempt is warranted.
