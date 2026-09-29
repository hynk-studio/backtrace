# Startup fail-fast: CPU implementation and evidence

Fresh Codex work on 2026-09-29 from merged main
`e5f3507ae91452ddac0ac14b990e5f4a2a517ed3` (tree
`d41dbcb53cb29366b33f13f96d0fb75a3c79bd74`), following the
[handoff](https://github.com/hynk-studio/backtrace/issues/1#issuecomment-5890369708)
and [PR #5 review](https://github.com/hynk-studio/backtrace/pull/5#pullrequestreview-5351238800).
Both previous attempts and the pre-allocation STOP remain historical and consumed.
No GPU, model request, provider allocation, payment or Kaggle operation occurred.

## Actual integration

The retained failure contained a worker `OutOfResources` (98,304 shared-memory
bytes required; 65,536 available), followed by `EngineCore failed to start`.
The API parent stayed alive; `adk-submission 0.2.11` only polls that parent's exit
and HTTP health, so it waited 1,200 seconds. Its own teardown extended `start()`
to 1210.852 seconds in the historical run.

`tools/startup_guard.py` subclasses the pinned wrapper's public `build_cmd`,
`is_healthy`, `start` and `stop` methods. **The official `start()` and readiness
loop still execute.** A tiny exec shim creates a dedicated POSIX session/group;
the original generated vLLM command follows unchanged. Health checks observe
fresh bounded records before and after the official loopback HTTP request.
No thread, wheel patch, model implementation or replacement launch loop.

Source inspection changed the detection rule: pinned vLLM
`multiproc_executor.py:949` logs a worker exception and **continues**. A complete
worker traceback alone therefore does not abort. A structured terminal engine
traceback (`core.py:1108`, handler re-raises) confirms failure. The observer keeps
the earlier worker cause only when the engine exception references that same
message; otherwise it reports the engine cause. Replaying the retained private
log recognized the original `OutOfResources`, not the later wrapper timeout.

The pinned wrapper truncates its newly created log before spawn. The observer
checks the log against the opened writer's inode, starts at byte zero of that
fresh stream, reads at most 256KiB per observation and caps trace context. It
ignores incomplete/oversized records, unstructured ERROR text, quoted tracebacks,
warnings, standalone recoverable worker failures and pre-start stale logs.
The private writer descriptor is a **version-pinned observation seam**, checked
against the actual installed wrapper; it is not claimed as a portable API.

Fatal evidence written during a health request wins before readiness is accepted.
After successful readiness there is no live observer to cancel it retroactively.
Readiness and remaining-total deadlines use monotonic time. The original health
request has a two-second timeout and the original poll interval is one second;
polling/HTTP and teardown latency remain separate from the logical deadline.
This is not a promise that `start()` returns exactly at its deadline.

Cleanup signals only the dedicated owned process group: TERM, at most one-second
grace, KILL if needed, wait/reap, and a bounded group-disappearance check. Repeated
cleanup is inert. Cleanup errors are recorded separately without replacing an
active causal startup exception. The existing private driver's UID/subreaper
cleanup remains responsible for descendants that deliberately leave the group;
this observer is neither a sandbox nor a provider-session termination mechanism.

`tools/guard_driver.py` provides a reproducible, hash-gated transform of the
retained no-custom-ar driver. It changes only constructor wrapping, copying the
authored helper to the existing private code directory, and observation reporting.
All module constants, including the embedded official serving/setup cells, are
byte-preserved. It refuses drift and existing output directories, never imports
or executes the driver and never creates an attempt marker. The generated driver
still has the old T4 assertions; it is an **integration demonstration, not an
authorized third T4 run or a launch-ready A100 driver**.

| Private artifact | SHA-256 |
| --- | --- |
| Retained original driver | `c7eda43a043535eed064b8f347bf271b22eb235c539e44dfe1633c43f47f5189` |
| Transformed driver, two identical preparations | `8c140418eaf4332e17e75fd5412f5d64d5350d3e3512011998e2b32a8b5a85c5` |
| Exact driver diff | `8de42027e70122788e0c85e22fe692c7c5e522866687f9cb0658a5dca294fa96` |

The helper hash, retained log identity, input pins, consumed-marker hashes,
source URLs/access times and detailed results are in
[startup-guard-evidence.json](startup-guard-evidence.json). Raw logs, official
code and transformed private drivers remain Git-ignored.

## Fresh execution results

**66 local tests passed**, Python 3.9.6 on macOS. The local lifecycle tests use
real disposable CPU processes and an explicitly authored lifecycle stand-in.
They are not evidence that an official wrapper or model ran.

**Nine separate official integration tests passed**, Python 3.12.14. Eight use
the real pinned `VllmServer` start/readiness/HTTP/stop paths; only the launched
payload and its environment are replaced by an authored CPU fixture. Test
startup/total caps are shortened; the real one-second poll interval is retained.
The ninth checks the actual retained driver transform, reproducibility, unchanged
constants and no-overwrite. Credentials are cleared, temporary files removed,
non-loopback connections denied in the test controller, and the process has a
60-second overall alarm. No vLLM module, real model or task repository is run.

| Actual-wrapper fixture | Detection after emitted fatal evidence | Teardown |
| --- | ---: | ---: |
| Worker/engine failure; API parent confirmed alive | 0.731233 s | 0.069183 s |
| Fatal during successful health response | 0.024499 s | 0.071814 s |
| Successful readiness | n/a; ready at 1.019658 s | 1.025779 s |
| Harmless/recoverable/quoted errors | no false abort | 1.028311 s |
| Stale prior log | no false abort | 1.033970 s |
| Readiness deadline / total deadline | finite timeout, no fatal classification | 0.225236 / 1.026813 s |
| TERM-resistant parent | n/a; KILL fallback exercised | 1.034570 s |

Each case confirmed an empty owned process group and absent parent/worker/leaf
PIDs after cleanup, including a second stop. Fatal detection met the explicit
**five-second CPU-test bound**, excluding teardown. The emitter stamps the shared
POSIX monotonic clock immediately before flushing the complete synthetic record,
so these are conservative delivery-to-detection bounds, not GPU measurements.
The shared POSIX clock avoids Python 3.9 macOS's process-local `monotonic()` origins.

**One real-wrapper argv test passed** on the actual six-file archive. With
injected T4/A100 capability and TP values, all settings remain equal except the
named TP/dtype delta; the guard preserves the original argv suffix. Initially
the extended assertion expected an explicit `--tensor-parallel-size 1`; the real
wrapper omits its default, so the assertion now verifies that actual behavior.
This is command construction, not hardware/dtype/backend execution.

Preflight READY; all 16 official artifact pins/ten starter files PASS; actual
candidate directory/model/includes/schema/generation/adapter checks PASS. The
existing compiler/binding probe was also rerun: PASS with its rejecting model
client and absent sandbox boundaries, no tool/model request.

Frozen candidate remains **6,230 bytes**,
`2e24495826cb971053439a00d9ad8350471fc0efffa41a54b82082feedaa7358`;
both retained builds match. Five-field input remains **810 bytes**,
`6ed92f4e646c17728aa8b9ca433a032d61b6b06827eec463a02c00f331c25d60`.
No repackaging, budget, task, prompt, adapter or AgentTool change.

## Commands and verification levels

Executed from the repository root (local receipts are under `.local/startup-guard`):

```sh
python3 -m unittest discover -s tests -v
python3 tools/backtrace.py preflight
python3 tools/backtrace.py verify-artifacts .local/official
.local/cpu-checks/bin/python tools/official_check.py .local/official --candidate .local/r0-clean/build-a.zip
python3 tools/compile_probe.py .local/official .local/r0-clean/build-a.zip --official-python .local/cpu-checks/bin/python
env -i PATH=/usr/bin:/bin LANG=en_US.UTF-8 .local/cpu-checks/bin/python -I -B tests/official_startup_guard.py
env -i PATH=/usr/bin:/bin LANG=en_US.UTF-8 .local/cpu-checks/bin/python -I -B tests/official_server_command.py
python3 tools/guard_driver.py .local/smoke/no-custom-ar/one_task.py .local/startup-guard/driver-final
git diff --check
git diff main...HEAD --check
```

All listed commands exit 0. Source inspection additionally used `zipfile` to read
the pinned wheel without imports, `FatalTrace.feed()` on the retained error log,
`hashlib.sha256` on listed local artifacts, public HTTP GETs and one read-only
GPU catalog GraphQL query (403). No provider mutation command was issued.

| Stage | This task |
| --- | --- |
| Local tooling | PASS, 66 tests |
| Official artifacts acquired/pinned | Existing pins reverified; no competition re-download |
| Candidate packaging/inspection | Existing frozen archive re-inspected; rebuild NOT RUN |
| Official CPU/schema and compiler/binding | PASS with explicit model/sandbox boundaries |
| Startup supervision | PASS, disposable CPU payload through actual wrapper |
| A100/Linux image or provider expiry | NOT RUN; proposal prerequisites only |
| GPU/model health/request, task/tools/patch/public tests | NOT RUN |
| Competition submission/acceptance, hosted scoring, training | NOT RUN |

These results are Codex's newly executed checks, separate from ChatGPT's historical
review and both historical GPU failures. The only proposed next run is in
[the conditional A10080-TP1 proposal](r0-a100-proposal.md).
