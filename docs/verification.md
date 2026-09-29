# No-custom-all-reduce continuation — startup failure, session terminated

Fresh Codex execution on 2026-09-29, continuing reviewed head
`6357b8e9525a786df166036f82f509dd715745a6` in existing Draft PR #5.
The [complete report](r0-no-custom-ar.md) records exact commands, private driver
hash/diff, first-error context, timings and the limits of each observation.
All earlier results below remain historical; neither GPU attempt was retried.

- **PASS: 51 local tests**, Python 3.9.6; five focused source regressions.
  **PASS: one real pinned-wrapper CPU command test**, with explicitly injected
  hardware capability. The real argv adds the flag once and preserves everything
  else. Preflight READY, 16 original pins and actual-candidate official checks PASS.
- **Frozen archive unchanged:** 6,230 bytes, SHA-256
  `2e24495826cb971053439a00d9ad8350471fc0efffa41a54b82082feedaa7358`.
  All selected inputs, model v2 and wheelhouse v25 hashes matched. No rebuild.
- **One additional private T4 x2 run:** SM75, native BF16 false, requested `auto`,
  observed FP16 and effective `disable_custom_all_reduce=True`. NCCL 2.27.5
  initialized; no per-collective tracing claim. Weight loading completed.
- **Startup FAILED:** graph profiling reached Triton attention, which required
  98,304 shared-memory bytes against a 65,536 limit. No prior custom-all-reduce
  error recurred, but graph profiling did not complete. The wrapper only surfaced
  the failure after its 1200-second health wait and stop handling: **1210.852 s**
  for `start()`, not an exact <=1200-second call. No configuration fallback.
- **Cleanup CONFIRMED:** zero worker survivors, temporary workspace removed,
  independent provider ERROR, CPU control off/None, no active events. Provider
  runtime **1536.5 s**; request-to-terminal readback **1564.903 s** bounds additional
  use at **0.86940 aggregate GPU-hours**. Quota **00:10 → 00:36 / 30 hrs**, $0 paid.
- **NOT RUN:** healthy served identity, alias/request/thinking parameters,
  returned model request, selected task, agent tools, public-test verification,
  competition submission/acceptance, hosted scoring and training. **No patch
  generated**, distinct from an empty patch. The real sandbox dependency check
  passed as preparation, not an agent tool invocation.

These are new Codex executions, distinct from ChatGPT's review checks. Historical
compiler/binding tests were NOT RERUN. Raw originals and both consumed guards are
retained privately; this additional authorization is consumed.

---

# Native-dtype continuation — GPU startup failure, session terminated

Fresh Codex execution on 2026-09-29, continuing the reviewed head
`2de98345c643651f6bdb38b425dd7f60ed2b9440` in Draft PR #5. The
[full execution report](r0-native-dtype.md) records exact commands, private driver
diff/hash, inputs, phase timing and boundaries; the manifest records acquired bytes.

- **PASS: 49 local tests** on Python 3.9.6, including three focused native-dtype
  regressions. CPU preflight, 16 original artifact pins, actual-candidate official
  CPU/schema checks and whitespace checks pass. No archive was rebuilt; its
  **6,230 bytes / `2e24495826cb971053439a00d9ad8350471fc0efffa41a54b82082feedaa7358`**
  remain frozen. Historical compiler/binding checks were not rerun.
- **PASS: concrete CPU prerequisites**, including selected-only input preparation,
  exact-image execution, real official sandbox dependency inheritance, credential
  separation and independent provider timeout (CPU sleep canceled at 72 s).
  Injected dtype-source tests are distinct from the actual GPU observations.
- **One actual T4 x2 attempt:** native BF16 false, requested `auto`, actual vLLM
  **FP16**. Weights loaded; CUDA custom-all-reduce returned `invalid argument`
  during graph profiling. Server startup **FAILED**, not an observed OOM or
  successful inference. Provider runtime **649.6 s**; no automatic rerun.
- **Cleanup CONFIRMED:** zero worker survivors, temporary workspace removed,
  independent provider `ERROR` terminal state, CPU control draft stopped/off.
  Quota readback **00:10 / 30 hrs**; paid spend **$0**. The wider observed
  request-to-terminal interval bounds use at **0.4561 aggregate GPU-hours**.
- **NOT RUN:** healthy serving identity, model request/alias/thinking parameters,
  selected task, agent tools, public-test verification, competition submission,
  hosted scoring and training. **No patch generated**, not an empty-patch result.

These are Codex's executions, not extensions of ChatGPT's independent review
checks. The pre-allocation STOP below remains historical evidence.

---

# Historical authorized smoke prechecks — GPU/model execution NOT RUN

2026-09-29 UTC, fresh Codex execution after PR #4 merged. Main/base
`d14a1542b7bb094f0e5bda7eb8482ddecafe8c57`, tree
`a5c552957e8e25c5f93966feed3fe5ebcd9d3868`; branch **bt-001-r0-smoke**.
The complete [attempt record](r0-smoke-attempt.md) distinguishes acquired bytes,
real Kaggle CPU metadata/session checks, a conditional source reproduction with
injected boundaries, and the unrun GPU stages. No training or submission ran.

- **PASS: 46 local tests**, Python 3.9.6, including five new synthetic task
  selection tests and a real CLI subprocess check. No reference answer is a test
  fixture. Preflight READY; 16 original artifact pins reverified.
- **PASS:** the selector independently reproduced the already-frozen
  `fastapi_11194` choice and the same 810-byte five-field input. Existing output
  rejection, duplicate conflicts and answer-field exclusion are tested.
- **PASS:** actual archived candidate official CPU/schema checks rerun. Its
  6,230 bytes and SHA-256 remain unchanged. No archive rebuilt. Compiler/binding
  probe and its six opt-in regressions were **NOT RERUN**; PR #4 evidence remains
  historical, not a newly completed milestone.
- **STOP before GPU allocation:** unchanged notebook dtype selection includes
  BF16 emulation, while the acquired vLLM CUDA guard rejects BF16 on SM75. The
  source reproduction injects device capability and successful tensor allocation;
  it is **not** a T4 execution, startup failure, OOM or model-fit measurement.
- Two finite Kaggle **CPU-only** prerequisite cells completed (20.02 seconds and
  4.296 seconds). Separate Kaggle **Stop session** actions returned the draft to
  **off**, accelerator **None**. These establish the observed manual control,
  not a tested unattended 1,800-second GPU-session expiry.
- Server/model loading, health, request/alias/thinking behavior, task tools,
  generated patch, public-test verification, submission and hosted scoring:
  **NOT RUN**. GPU allocation/use **0**, paid spend **$0**.

Exact commands, source pins, conditional limitations and remaining prerequisites
are in the attempt record. These results are Codex's executions and do not extend
ChatGPT's independent Python 3.13.5 review checks.

---

# Historical PR #4 CPU compiler/binding probe

2026-09-29 UTC, executed by Codex. Read the complete
[post-merge handoff](https://github.com/hynk-studio/backtrace/issues/1#issuecomment-5882380242),
current AGENTS.md, Issue #1 and PR inventory. Origin remains
`https://github.com/hynk-studio/backtrace.git`. PR #3 is merged; no PR was open at
start. Fast-forwarded clean local main to
`cddafaa6916560208b8782e9c2adf42e331d6d5c`, tree
`a7b6d3cf392eb8c6738a791638e1649f17d03b94`, then created **bt-001-cpu-binding**.
The merged branch, source pins, CPU dependency lock, original starter and frozen
candidate are unchanged. No new dependency, model or task data was downloaded.
The new Draft PR report records the final head/tree without a self-referential
commit hash in this file. Issue #1 stays open; no merge or auto-merge is authorized.

## Current verification levels

| Stage | Result in this slice |
| --- | --- |
| Local tooling | **PASS: 41 tests**, Python 3.9.6; preflight READY. |
| Official artifacts | **PASS: 16 pins**, ten original starter files; no new acquisition. |
| Candidate packaging/local inspection | Existing frozen archive re-inspected, **6,230 bytes**, hash unchanged; build-a/build-b still identical. **No rebuild** in this slice. Prior reproducible builds remain PR #3 evidence. |
| Official candidate CPU/schema checks | **PASS**, rerun on actual archived candidate, Python 3.12.14/macOS arm64, same pinned environment. |
| Actual compiler/construction | **PASS**: real official compiler, builders, model/tool resolvers, registry and two LlmAgents. Request client and absent sandbox boundaries below. |
| Callable/schema binding | **PASS**: nine real registered callables; 13 FunctionTool declarations and one existing AgentTool declaration. No tool body executed. |
| Focused official integration regressions | **PASS: 6**, real compiler with authored synthetic fixtures; unknown model/tool rejection and denied generation/network/process checks. |
| Tool/sandbox execution; model/server execution | **NOT RUN**. No tool bodies, server start, checkpoint/tokenizer load or provider completion. |
| Public task verification; Kaggle execution/submission acceptance; hosted scoring; training | **NOT RUN**. |

Candidate SHA-256 remains
`2e24495826cb971053439a00d9ad8350471fc0efffa41a54b82082feedaa7358`.
Both agents preserve the exact prompt hashes in [r0.md](r0.md), sampling and
no-adapter selection; root AgentTool retains `skip_summarization=True`. The
runtime budget maps to **60 command seconds / 10 tools / 1 minute / 50 turns**.
The actual model registry targets the explicit version-2 absolute path with the
notebook's `openai/` prefix; no helper/fallback path is used. The compiler's
enable_thinking bridge is observed, not proof of wire-level thinking-budget enforcement.

The official ModelRegistry, LiteLlm, AgentTool, FunctionTool and
AdkSandboxCodeExecutor are real objects. The **injected** NoRequestClient raises
on completion; it provides no fabricated response. Context uses authored task
strings, no real task record and **sandbox=None**. VllmServer is constructed but
never started. Installed official Python source is checked against the acquired
wheels before imports. Python socket/process audit guards operate in a sanitized
child, not an OS sandbox. IPv6 capability detection is disabled in that child to
avoid urllib3's import-time bind. Final actual-candidate probe: **zero forbidden
attempts**, no server process, temporary root/log cleaned, archive hash unchanged.

Initial construction attempts failed closed because urllib3's IPv6 import probe
tried to bind a socket; urllib3 caught the denied operation, and the probe's
attempt counter still rejected the run. An authored diagnostic was added and
that import capability test was disabled. No official wheel was patched and no
network exception was allowed. Subsequent construction passed. The negative
generation fixture enters real LiteLlm request preparation and stops at the
injected client; this is not a model/provider request or an inference result.

## Exact verification commands and outcomes

From `/Users/hynk/code/backtrace`:

```sh
python3 -m unittest discover -s tests -v
python3 tools/backtrace.py preflight
python3 tools/backtrace.py verify-artifacts .local/official
.local/cpu-checks/bin/python tools/official_check.py .local/official --candidate .local/r0-clean/build-a.zip
python3 tools/compile_probe.py .local/official .local/r0-clean/build-a.zip --official-python .local/cpu-checks/bin/python > .local/compile-probe.json
env -i PATH=/usr/bin:/bin LANG=en_US.UTF-8 .local/cpu-checks/bin/python -I -B tests/official_binding.py
shasum -a 256 .local/r0-clean/build-a.zip .local/r0-clean/build-b.zip .local/starter.ipynb
stat -f '%z %N' .local/r0-clean/build-a.zip .local/r0-clean/build-b.zip
cmp .local/r0-clean/build-a.zip .local/r0-clean/build-b.zip
.local/cpu-checks/bin/python -m pip check
git diff --check
git diff main...HEAD --check
```

Final checks exit **0**, except `pip check` remains **1**, exactly the four known
unused swegemma requirements: accelerate, safetensors, torchvision, transformers.
No new conflict or attempt to install a GPU/inference stack. Preflight and the
old official schema check correctly report stages outside their own command
scope as NOT RUN; they do not read/cache the new construction result.

Also reverified all **137** installed CPU dependency versions and retained wheel
hashes (exit 0), without importing those dependencies:

```sh
.local/cpu-checks/bin/python - <<'PY'
import hashlib, json
from importlib.metadata import version
from pathlib import Path
pins = json.loads(Path('docs/cpu-environment.json').read_text())['artifacts']
for item in pins:
    assert version(item['artifact']) == item['version'], item['artifact']
    data = Path(item['local_path']).read_bytes()
    assert len(data) == item['size_bytes']
    assert hashlib.sha256(data).hexdigest() == item['sha256']
print('137 CPU dependency versions and retained wheel hashes: PASS')
PY
```

The four new standard-library tests check denied/redacted operations, sanitized
child arguments, cleanup on mocked child failure/timeout and a real CLI missing
environment diagnostic. Mocked process tests do not establish official behavior;
the separate actual-candidate probe does. The six opt-in integration regressions
use installed official classes and authored fixture YAML; none execute a tool.
All packaging, no-overwrite, exact-delta, cleanup and generic ZIP safety tests
still pass. No claim here extends ChatGPT's earlier independent Python 3.13.5
checks; these are fresh Codex executions on the versions listed above.

[The prepared smoke recipe](r0-smoke.md) records actual account resource evidence,
the v2 checkpoint, deterministic public-task selection rule (ID unresolved),
minimal inputs, explicit driver/hardware deviations and finite caps. It is
**NOT RUN**. The CPU result does not establish Kaggle allocation, model fit,
tool execution, task success, hosted acceptance or any performance benefit.

---

# Historical PR #3 R0-clean implementation and candidate checks

2026-09-29 UTC. This checkpoint supersedes the prior recipe blocker. Read the
[ChatGPT review](https://github.com/hynk-studio/backtrace/pull/3#pullrequestreview-5346432812)
and [Issue #1 correction](https://github.com/hynk-studio/backtrace/issues/1#issuecomment-5881567240)
before implementation. The variant was explicitly authorized; no new approval,
artifact acquisition, desktop work, credential, model or paid resource was needed.

## Repository identity

Clean branch `bt-001-r0-artifacts`, origin
`https://github.com/hynk-studio/backtrace.git`, reviewed/local/remote head
`5b65d692ddc9e18d953989b1cbe978a75646e2b4`, tree
`6508c9a68e47e0673a682b5b03c9960bccd45131`. Base/main remains
`757b56f29ee8bcb6c9379b4d90525b10c0366a74`, tree
`db667aa37bea445c822748918adc91a5dded3906`. PR #3 was the only open PR,
Draft with no auto-merge request; Issue #1 was open. Current AGENTS.md, issue,
review, PR, worktree, branches and remote refs were inspected. This update uses
the existing PR and preserves its prior work. The PR report records the new commit
and tree after commit creation; this document cannot contain its own commit hash.

## Current verification levels

| Level | Observed result |
| --- | --- |
| Local tooling | PASS: **37 tests**, Python **3.9.6**; preflight exit 0. |
| Official acquisition/pinning | PASS: existing **16** guide/starter/wheel pins reverified; unchanged ten-file original. No new download. |
| R0-clean packaging/local inspection | PASS: two independent builds, byte-identical **6,230-byte** ZIPs, exact six-file closure and authorized delta. |
| Official CPU validation: original | PASS: Python **3.12.14**, ten files, both schemas, model, includes, generation limits and two adapters. |
| Official CPU validation: actual candidate | PASS: same pinned environment; six archived files, exact delta, directory/model/includes/both schemas/generation checks, both effective adapters absent and discovery empty. |
| Compiler/tool binding | **NOT RUN**. Existing AgentTool bytes preserved; compilation has not been exercised. |
| End-to-end model execution | **NOT RUN**. |
| Kaggle submission acceptance | **NOT RUN**. |
| Hosted scoring | **NOT RUN**. |

Both ZIPs have SHA-256
`2e24495826cb971053439a00d9ad8350471fc0efffa41a54b82082feedaa7358`.
[The R0 recipe](r0.md) lists member hashes and exact two-line/four-file delta.
All other retained bytes, prompts, sampling, budgets and AgentTool wiring are
unchanged. The ten-file official reference remains local, intact and distinct
from the six-file experimental derivative. All competition assets, candidate ZIPs
and local receipts remain Git-ignored; no redistribution or license assumption changed.

These are **Codex's executions**, not an extension of ChatGPT's independent
Python 3.13.5 review (24 tests against the earlier source). That review did not
independently rerun the gated artifact/CPU checks. Synthetic unit tests mock the
official checker where necessary and do not count as official validation; the
separate actual-artifact CPU commands below provide that evidence.

## Commands and outcomes

From `/Users/hynk/code/backtrace`:

```sh
python3 -m unittest discover -s tests -v
python3 tools/backtrace.py preflight
python3 tools/backtrace.py verify-artifacts .local/official
.local/cpu-checks/bin/python tools/official_check.py .local/official
mkdir -p .local/r0-clean
python3 tools/backtrace.py baseline .local/official .local/r0-clean/build-a.zip --official-python .local/cpu-checks/bin/python > .local/r0-clean/build-a.receipt.json
python3 tools/backtrace.py baseline .local/official .local/r0-clean/build-b.zip --official-python .local/cpu-checks/bin/python > .local/r0-clean/build-b.receipt.json
cmp .local/r0-clean/build-a.zip .local/r0-clean/build-b.zip
shasum -a 256 .local/r0-clean/build-a.zip .local/r0-clean/build-b.zip
.local/cpu-checks/bin/python tools/official_check.py .local/official --candidate .local/r0-clean/build-a.zip
.local/cpu-checks/bin/python -m pip check
git diff --check
git diff main...HEAD --check
```

All final commands exit **0** except the intentionally incomplete CPU environment's
`pip check`: exit **1**, exactly the same four omitted swegemma dependencies
(accelerate, safetensors, torchvision, transformers), with no new conflicts.
No GPU/inference dependency installation was attempted.

The first two packaging attempts and one diagnostic reproduction failed closed
with official `PathTraversalError`, leaving zero ZIPs. Cause: macOS temporary
paths used `/var` while the official loader resolved the sandbox to `/private/var`.
The checker now resolves its temporary root before supplying paths to the official
loader. No source file, include or official validation rule was changed to fix it.
Both subsequent builds and the explicit candidate recheck passed.

Real subprocess negative checks ran from an empty temporary cwd with
`python3 -B /Users/hynk/code/backtrace/tools/backtrace.py` followed by:

- `baseline`: exit 2, actionable required-input message, empty stdout, zero files.
- `verify-artifacts private-missing`: exit 2, authored acquisition guidance,
  empty stdout, no echoed private path, zero files.
- `baseline /Users/hynk/code/backtrace/.local/official failed.zip --official-python <current non-venv sys.executable>`:
  exit 2 at official CPU checks; no final ZIP or staging directory remains.
- `baseline /Users/hynk/code/backtrace/.local/official /Users/hynk/code/backtrace/.local/r0-clean/build-a.zip --official-python /Users/hynk/code/backtrace/.local/cpu-checks/bin/python`:
  exit 2; existing candidate hash unchanged (no overwrite).
- `baseline /Users/hynk/code/backtrace/.local/official /Users/hynk/code/backtrace/.local/official/sample_submission/candidate.zip --official-python /Users/hynk/code/backtrace/.local/cpu-checks/bin/python`:
  exit 2; destination overlaps the immutable reference; zero files created.

The CLI diagnostic was also compared using temporary copies of `tools/backtrace.py`
and `tools/artifacts.py` from `git show 5b65d692ddc9e18d953989b1cbe978a75646e2b4:<path>`.
Both old and current commands exit 2 with empty stdout. Before: generic
unsafe/unreadable-artifact fallback. After: `FAILED: missing artifact directory;
follow docs/r0.md acquisition steps`. A shared authored exception definition fixes
the script/import identity mismatch without weakening redaction. The committed
regression executes the real CLI, checks exact stderr and asserts no output writes.

The 13 new focused tests cover exact delta and reference preservation, AgentTool
bytes and contained parent includes, deterministic metadata/hash, input/config/adapter
drift, declaration location/multiplicity, existing-output and publication-race
protection, resolved output aliases, failed-check cleanup, candidate mutation,
missing/extra/reintroduced-adapter files, invalid CPU receipts, missing CLI inputs
and actual archived-byte selection/temporary cleanup in the CPU wrapper. Existing
pinning and ZIP safety regressions continue to pass; the generic inspector's
safety checks and local limits are unchanged.

Next action: ChatGPT review of the updated Draft PR #3 and its candidate evidence.
The next research execution milestone remains a separately authorized bounded
model smoke run; this task did not execute or authorize it.

---

# Historical PR #3 artifact acquisition checkpoint

2026-09-29 UTC. Current results below supersede the historical bootstrap access
blocker. The prior PR #2 report is retained further below; its Python 3.9.6 checks
and the reviewer's Python 3.13.5 checks are separate from this execution.

## Repository and authority

Started at clean `main` in `/Users/hynk/code/backtrace`, origin
`https://github.com/hynk-studio/backtrace.git`, main/base
`757b56f29ee8bcb6c9379b4d90525b10c0366a74`, tree
`db667aa37bea445c822748918adc91a5dded3906`. Read AGENTS.md, Issue #1 and its post-merge
checkpoint, owner access confirmation, PR #2 merge state and open PR inventory.
No open PRs or intervening tracked changes were present. New issue branch:
`bt-001-r0-artifacts`. The bootstrap exception was not reused. No main or merged-PR
changes, force push, issue closure or merge action occurred.

## Current verification levels

| Level | Observed result |
| --- | --- |
| Local tooling | PASS: 24 unittest tests on Python 3.9.6 (18 existing plus 6 authored artifact-pin regressions); preflight exit 0. |
| Official artifact acquisition/pinning | PASS for guide, complete ten-file starter and five relevant wheels (16 artifacts). Model/tokenizer and full hosted image are not acquired. |
| Candidate packaging/local archive inspection | NOT RUN: no-LoRA conflicts with adapter-equipped notebook v2; explicit variant decision pending. No archive produced. |
| Official CPU validation | PASS on **unchanged original starter**, Python 3.12.14: competition directory limits, single model, include resolution, both schemas, generation constraints and adapter discovery. Not a no-LoRA candidate result. |
| Compiler/tool binding | NOT RUN. |
| End-to-end model execution | NOT RUN. |
| Kaggle submission acceptance | NOT RUN. |
| Hosted scoring | NOT RUN. |

The selected reference is notebook v2, source SHA-256
`0c54c3bac3269e422b1d48ac8087ff26b49fe764231b7983c90ef842382f9a87`.
Its sampling literal equals the current sample's 120-byte configuration. The
original has two real adapters. No removal/variant substitution is authorized
by inference; the proposed no-LoRA deviation is recorded in [r0.md](r0.md).
All downloaded third-party bytes remain ignored. Public files are authored code,
notes and acquisition/environment manifests, without a license choice.

## Commands and observed outcomes

Repository inspection used `pwd`, `git remote -v`, `git status --short --branch`,
`git branch -avv`, `git worktree list --porcelain`, `git ls-remote --heads origin`,
`git rev-parse HEAD`, `git rev-parse HEAD^{tree}`, `gh issue view 1 --repo
hynk-studio/backtrace --comments`, and GitHub JSON issue/PR queries. Current
repository instructions and existing source documents were read before mutation.

```sh
git switch -c bt-001-r0-artifacts
python3 -m unittest discover -s tests -v
python3 tools/backtrace.py preflight
python3 tools/backtrace.py verify-artifacts .local/official
.local/cpu-checks/bin/python tools/official_check.py .local/official
python3 tools/backtrace.py baseline
git diff --check
git diff main...HEAD --check
```

Results respectively: branch created; **24 passed**; local READY (0); **16 pins,
10 starter files PASS** (0); official CPU checks **PASS on original starter** (0);
baseline expected **2**, no archive; both diff checks passed. A separate baseline
subprocess with an empty temporary cwd returned 2 and left zero files. Missing,
altered, extra, aliased and symlink input cases are synthetic local tests. Existing
ZIP duplicate/alias/traversal/collision/content checks remain unchanged and pass.
Preflight does not run or cache the separate official check, so its NOT RUN field
refers to that command's scope.

At acquisition, `kaggle competitions files gemma-4-developer-agent` returned
127 (CLI absent). Installed Kaggle 2.2.4 in an ignored, isolated CLI venv using
bundled Python 3.12.14. `.local/kaggle-cli/bin/kaggle --version` printed 2.2.4;
`.local/kaggle-cli/bin/kaggle competitions files gemma-4-developer-agent` returned
1 (API authentication required). Presence-only checks found no supported Kaggle
credential environment/file. No secret contents were printed or copied. Existing
Google sign-in in the dedicated Chrome tab restored Kaggle website access without
new credentials or terms. Per-file Download controls acquired the guide/starter
and five wheelhouse files; **Download all files was never used**. The browser's
download-event observer timed out once although HARNESS_README.md was successfully
saved; file size/hash and source contents confirmed acquisition. Notebook v2 Input
explorer supplied a second, byte-identical swegemma wheel. The temporary keep-awake
lease was stopped after browser acquisition.

CPU environment commands (from repository root):

```sh
/Users/hynk/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m venv .local/cpu-checks
.local/cpu-checks/bin/python -m pip install --disable-pip-version-check --dry-run --only-binary=:all: --report .local/cpu-install-plan.json .local/official/wheels/adk_submission-0.2.11-py3-none-any.whl .local/official/wheels/google_adk-1.36.1-py3-none-any.whl .local/official/wheels/google_genai-2.11.0-py3-none-any.whl
.local/cpu-checks/bin/python -m pip install --disable-pip-version-check --only-binary=:all: --report .local/cpu-install-report.json .local/official/wheels/adk_submission-0.2.11-py3-none-any.whl .local/official/wheels/google_adk-1.36.1-py3-none-any.whl .local/official/wheels/google_genai-2.11.0-py3-none-any.whl
.local/cpu-checks/bin/python -m pip install --disable-pip-version-check --only-binary=:all: --report .local/cpu-extra-install-report.json .local/official/wheels/adk_eval_core-0.1.0-py3-none-any.whl 'litellm==1.83.14' networkx cachetools pandas
.local/cpu-checks/bin/python -m pip install --disable-pip-version-check --no-deps .local/official/wheels/swegemma-0.2.7-py3-none-any.whl
.local/cpu-checks/bin/python -m pip download --disable-pip-version-check --no-deps --only-binary=:all: --require-hashes -r .local/cpu-download-lock.txt -d .local/cpu-wheels
.local/cpu-checks/bin/python -m pip install --disable-pip-version-check --no-deps --require-hashes --only-binary=:all: -r docs/cpu-requirements.txt
.local/cpu-checks/bin/python -m pip check
```

Install/download commands exited 0; their stdout/stderr were retained in ignored
`.local/cpu-*.log` files. `pip check` exited 1 listing four deliberately omitted,
unused inference dependencies: accelerate, safetensors, torchvision, transformers.
This is a CPU-only import/check environment, not a complete inference installation.
The initial official checks were also invoked directly using sanitized `env -i`
Python heredocs before adding the reproducible script. They reported the same ten
files, model alias and two schema/adapter results. Only the final script additionally
checks installed official source bytes and generation constraints. No package
import result is being presented as model execution or hosted acceptance.

Python stdlib inspection used `zipfile` to check wheel member names/types and read
source/metadata without imports, `hashlib.sha256` on retained bytes, and `ast.parse`
to read the notebook's sampling string without executing cells. The later official
check imports only the inspected CPU validation path in its isolated environment.
There was one failed shell read from a nonmatching speculative validator filename;
actual package inventories were then used. No alternate generic schema was used.

At that checkpoint, packaging was deferred pending the variant correction.
That planning conflict is resolved in the R0-clean checkpoint above.

---

# Historical PR #2 verification

2026-09-29 Asia/Seoul. Local execution: macOS, Python 3.9.6, standard library
only. No installed dependencies, model execution or paid services.

## Repository evidence

Initial cwd/root: `/Users/hynk/code/backtrace`; origin:
`https://github.com/hynk-studio/backtrace.git`. Local main was unborn, worktree had
no files, remote refs and GitHub branches were empty, and no existing PRs were
listed. Issue #1 was OPEN; no comments were returned. No repository/ancestor
AGENTS.md was found; the user-supplied global instructions applied.
GitHub reported `allow_auto_merge: false`.

The authorized exception created exactly one empty commit on main:
`2e0689eaf6fa23bb3de7d70832f3ee334b2e8180`. All substantive files belong to `bt-001-bootstrap`.
Final base/head/tree and Draft PR identity are reported in the PR/closeout rather
than embedded recursively in their own commit.

## Independent verification levels

| Level | Observed result |
| --- | --- |
| Local tooling tests | PASS: 18 unittest tests after the bounded allowlist correction, including adversarial synthetic ZIPs and mocked acquisition pin/overwrite checks. |
| Official requirements/starter acquired and pinned | PARTIAL: rendered primary pages inspected; complete notebook v2 source acquired/pinned and reacquired. Starter directory, harness guide/implementation and model bytes NOT ACQUIRED. |
| Candidate archive built and locally inspected | NOT RUN. Synthetic unit-test ZIPs are not candidates. |
| Official validator | NOT RUN: implementation/dependency bytes and starter missing. |
| Permitted end-to-end task | NOT RUN: no model/harness execution. |
| Kaggle submission accepted | NOT RUN: submission is not authorized. |
| Hosted scoring completed | NOT RUN. |

`preflight` reports local READY, official baseline BLOCKED. `baseline` returns
exit 2 with actionable missing-artifact instructions and no archive. Public
notebook acquisition returns version 2 and SHA-256
`0c54c3bac3269e422b1d48ac8087ff26b49fe764231b7983c90ef842382f9a87`;
reacquisition completed at `2026-09-28T19:56:09.575001+00:00`.

The first test run had one failed NUL-path fixture because Python's ZIP writer
truncates NUL filenames before serialization. The fixture was corrected by
mutating actual ZIP filename bytes; the inspector's truncation rejection then
passed. A subsequent metadata-rejection check raised the total from 14 to 15.
No official starter/validator test failures are claimed: those checks never ran.

## PR #2 bounded allowlist correction

Read the current instructions, Issue #1 and ChatGPT review before this repair.
The clean local branch and remote PR head matched reviewed commit
`c89bf82ef99e6596faa29e47c270e8f3c1f81a46`, tree
`285ce169d3e88a789556310782b5d32c0c027ef8`; there was no intervening work.

On local Python 3.9.6, new regressions reproduced the defect before the fix:
with either `notes.txt` or `Notes.txt` alone in a synthetic ZIP, the ambiguous
allowlist containing both names was accepted by the public function and the CLI
exited 0. The 18-test run reported four failing subtests. After rejecting distinct
allowlist names with the same canonical key and comparing exact member names for
completeness, both function cases raise `InspectionError` and both CLI cases exit
2. Ordinary exact allowlists still pass through both interfaces. Canonical keys
remain in use for archive aliases and file/directory collisions. Fixture bytes
remain unchanged, no files are extracted, and all existing safety tests pass.

Repair commands and observed results:

- `python3 -m unittest discover -s tests -v`: PASS, 18 tests after the fix.
- `python3 tools/backtrace.py preflight`: exit 0, local READY / official baseline BLOCKED.
- `python3 tools/backtrace.py baseline`: expected exit 2; no archive. A separate
  subprocess invocation in an empty temporary directory also left it empty.
- `git diff --check`: PASS.
- `git diff main...HEAD --check`: PASS.

These are Codex's Python 3.9.6 checks. The reviewer's independent Python 3.13.5
checks covered the original 15 tests and the reviewed source blobs, not this fix.
Notebook acquisition and Kaggle source inspection were not rerun during the
repair. All NOT RUN stages and missing-artifact limitations above remain intact.

## Exact inspection, acquisition and verification commands

Commands below were executed from the repository root (individual shell calls
sometimes batched commands with `&&`). File-authoring heredocs are not test or
execution evidence.

```sh
pwd
git remote -v
git status --short --branch
git branch -a
git ls-remote origin
rg --files -g AGENTS.md -g '!node_modules' -g '!vendor' .
git rev-parse --show-toplevel
git ls-remote --heads --tags origin
gh api repos/hynk-studio/backtrace --jq '{default_branch, size, allow_auto_merge}'
gh api repos/hynk-studio/backtrace/branches
ls -la
python3 --version
for p in /AGENTS.md /Users/AGENTS.md /Users/hynk/AGENTS.md /Users/hynk/code/AGENTS.md; do if test -f "$p"; then cat "$p"; fi; done
gh issue view 1 --repo hynk-studio/backtrace --json title,body,url,state
gh issue view 1 --repo hynk-studio/backtrace --comments
gh pr list --repo hynk-studio/backtrace --state all --json number,title,state,isDraft,url
git -c core.hooksPath=/dev/null commit --allow-empty -m 'chore: establish empty PR base'
git push origin main
git switch -c bt-001-bootstrap
python3 -m unittest discover -s tests -v
python3 tools/backtrace.py preflight
python3 tools/backtrace.py acquire-notebook .local/starter.ipynb
python3 tools/backtrace.py baseline
git diff --check
git status --short --ignored
git ls-tree main
git log --oneline --all
```

The initial `rg --files` returned exit 1 because there were no files, not because
an existing instruction was ignored. A focused memory lookup for Backtrace also
returned no matches; no project decisions were taken from another repository.

Source acquisition initially used Python `urllib.request.urlopen` with a
20-second timeout and a 2,000,001-byte bounded read for each URL in the manifest,
then `hashlib.sha256` on retained response bytes. HTML parsing exposed only page
titles. The public notebook API response was decoded with `json.loads`; the
`blob.source`/`sourceNullable` string was UTF-8 encoded unchanged and hashed.
The committed `acquire-notebook` command reproduces that source acquisition and
checks both version and source hash. It was executed successfully, independently
of mocked tests. No notebook cells were executed.

The web reader attempted all six Issue #1 URLs. Browser navigation then read the
rendered notebook, overview/model rules, rules, data description and welcome,
using accessibility snapshots or `#site-content` inner text. The data viewer
showed a sign-in/rules-agreement gate. No Join, agreement, submission or download
control for competition data was activated. The temporary browser tab was closed.
Browser-rendered content has no retained byte hash; downloaded HTML shell hashes
must not be used as hashes of that content. See the source manifest for exact
URLs, timestamps, identifiers and response-byte hashes.

## Limits and next action

ZIP checks are conservative local heuristics, not exhaustive secret detection or
official compliance. No binary adapter is permitted by this local inspector yet.
A caller allowlist needs independent provenance/content review; renaming or
encoding sensitive material can evade heuristic content checks. Source/terms
changes require reinspection. No claim of baseline performance, adapter
compatibility, synthetic competence or real-task transfer is supported.

Recommended next action: have the owner resolve Kaggle access/terms and obtain
`HARNESS_README.md`, `sample_submission/` and versioned harness packages for a
bounded contract-completion and R0 follow-up.
