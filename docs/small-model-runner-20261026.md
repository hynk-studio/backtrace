# Isolated CPU inference collector and evaluator connection

Date: 2026-10-26. Refs [BT-001](https://github.com/hynk-studio/backtrace/issues/1).
Base: Draft #32, `5ad61b43d1cda581e7651c7def9aaea88f5c461b`.

The previous stage prepared fixed E2B/E4B inputs but did not collect model
outputs. This stage implements the CPU inference-to-evaluation path, preserves
raw outputs and incomplete assignments, and qualifies failure boundaries with
authored controls and tiny random models. It does not download pretrained
weights, use a GPU, train a model or establish task performance.

## Execution contract

`tools/small_model_runner.py` reconstructs and compares the fixed smoke or
screening input bytes, selected families/episodes, model revisions, budgets and
tokenization report. Within each model it interleaves B0/B1 for each fixed input;
E2B precedes E4B. There is no selection based on output, retry, replacement or
unreported truncation. The original 36/288-request assignments remain intact.
They are development probes, not independent confirmatory samples.

The standalone worker sees only read-only system/Python libraries, its own
script, the approved tokenizer, a checkpoint and a job description. Messages
arrive over a bounded pipe; IDs and token digests are transport fields, not
model text. The host repository, evaluator, labels, credentials and output
directory are not mounted. Private user/PID/network/IPC/UTS namespaces, an empty
mount tree, namespace UID/GID 65532, no effective capabilities, no-new-privileges
and disabled nested user namespaces bound the worker. The coordinator is trusted
root on native Linux. This is a concrete input-isolation policy, not a claim to
resist a malicious host/kernel. No GPU device nodes are exposed.

Approved asset files are copied into a disposable, traversable staging directory
and mounted read-only. This resolves the observed namespace-UID/private-parent
permission conflict without changing source or evaluator directory permissions.
The allowlist contains public model/tokenizer files, the fixed worker and a job
configuration; it excludes prompts, labels and credentials. Normal cleanup
removes these copies. The parent-loss qualification supervisor removes registered
copies after proving the worker namespace is gone. An independently killed
unsupervised coordinator may leave these non-secret copies until host cleanup;
process termination and file cleanup are distinct properties.

The approved Python environment is installed in a dedicated traversable runtime
directory outside the private research tree. Its wheel installation remains
hash-locked. The launcher rejects private runtime ancestors without changing
their permissions, and the early native probe uses this same runtime path.

The worker re-tokenizes every input and requires the exact prior count and token
digest. It loads offline without remote code, rejects missing/mismatched text
weights and preserves the full output-token sequence. The coordinator decodes
those IDs independently and requires an exact raw-text match. It removes at most
one terminal token 1/106. Tool token 50, thought content, missing termination,
length-limit output, malformed/duplicate-key/nonfinite JSON and fenced JSON do
not become repaired answers. The original text and token IDs remain available.
Transport OK means parseable JSON, not a correct task answer; the existing exact
scorers separately enforce response schemas and task correctness.

Nonblocking input/output pipes share an absolute deadline, including model
startup. Each request also has a fixed ceiling. After timeout, worker failure or
protocol violation, execution stops and later assignments are NOT_RUN. There
is no automatic second model allocation or retry. The collector's CPU subrun
deadline is not a provider allocation timer and does not authorize a paid run.

An assignment file is written before launch. STARTED/FINISHED ledger records are
flushed and fsynced after every event; received wire frames and original raw
tokens/text are retained. If the coordinator dies, recovery reads that ledger,
preserves finished responses, marks an in-flight request INTERRUPTED and leaves
the remainder NOT_RUN. It preserves a partial final ledger line as evidence,
does not invent its contents and never reruns a request. Namespace parent-death
handling and explicit deadline cleanup are tested with detached descendants.

## Evaluation and evidence separation

For model outputs, only after the worker closes does the trusted evaluator generate references for
the already selected development inputs. Both static and temporal scorers keep
their original bytes and complete episode groupings. The report contains fixed
assignment-denominator scores and separate received-only case metrics. Missing
execution retains protocol penalties in the former; it is not interpreted as a
wrong answer actually produced by the model. Coverage and process status remain
visible. Confidence intervals and capability claims are NOT ESTABLISHED.

Qualification uses two explicit modes. `scripted_control` deliberately transports
authored oracle or invalid responses; it is allowed to receive authored token
IDs and can never be labeled a pretrained-model result. `random_fixture` uses
the real tokenizer vocabulary and actual fixed input lengths, with two-layer
random models derived from each candidate configuration and a two-output-token
cap. It performs actual PyTorch loading/generation/decoding through the same
worker and collector, but tests neither full-size resource feasibility nor
pretrained quality. The prior stage separately checked full layer layouts.

`pretrained_cpu_factory` is a local-only CPU entry requiring the exact complete
checkpoint SHA-256/size and both pinned configurations before mounting three
approved files. It has no downloader, provider client, training or GPU path.
Its byte-verifier has synthetic positive/negative controls; full pretrained
loading and generation through this entry remain NOT RUN. GPU device isolation,
the CUDA installation and resource measurements still need their own checks.

## Qualification and reproduction

The [native workflow](../.github/workflows/small-model-runner-cpu.yml) runs the
complete Linux test suite and preflight, installs the existing hash-locked CPU
runtime offline, acquires pinned tokenizer/header metadata, reconstructs and
re-tokenizes the existing inputs, then executes:

```sh
sudo env HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false "$BACKTRACE_CPU_RUNTIME/bin/python" -m tools.small_model_runner_probe .local/model-sources .local/packets .local/tokenization.json .local/smoke .local/runner-qualification
```

Use a fresh output directory. The coordinator must have native namespace
capabilities; there is no unisolated fallback. The runtime installation recipe
is in the workflow and [previous readiness report](small-model-readiness-20261026.md).
Bubblewrap's installed version and executable hash are recorded with each run;
OS-tool changes need new qualification, independently of Python wheel hashes.

Native controls cover exact authored oracle scoring, invalid tool-boundary
outputs, response timeout after one success, worker crash, wrong response ID,
oversized output, startup timeout, actual coordinator death/recovery and both
random-model runs. Boundary probes attempt host-label/repository/procfs reads,
host-loopback access, mounted-file mutation, UID escalation and nested user
namespaces; detached children must stop after deadline and parent loss.

Initial local findings are retained: a shortened random fixture inherited
out-of-range per-layer overrides from the full configuration; removing those
fixture-only overrides allowed both random checkpoints to be created. The
next local attempt stopped at namespace setup (a required procfs namespace path
was absent); a direct shell probe also reported NETLINK_ROUTE permission denied.
Neither ran isolated inference. The initial local focused suite passed 15 tests;
the final focused suite, including asset exclusion and runtime-ancestor permission
regressions, is checked separately. The local full suite attempted 590 tests with 5 failures,
10 errors and 4 skips in existing pip-fixture/startup/procfs checks; it remains
a failed local result.

Initial native run 40323532972 at
`84039d08438280958b060d9d5109a143fd476605` passed all 590 tests and preparation,
then failed before the boundary worker entered. Its artifact omitted the inner
boundary log; that diagnostic gap was corrected. The early diagnostic run
40324725974 at `4a49ebfe6144567d7d0e8533e9271d87fc86a964` retained the precise
mount-source Permission denied error. Asset staging fixed that failure, and the
corrected native boundary precheck passed. Run 40326406879 at
`8ab6dae167221d976fcd0213ffdb21ecfb7c66c3` then passed 591 tests and preparation,
but the real runtime beneath private `.local` failed with the same permission
class. The runtime is now installed outside that private tree, with an explicit
early traversal check and same-runtime boundary probe. These failed runs do not
establish a completed inference path.
Local full-suite and exact-source native results are recorded separately in the
final evidence receipt; native qualification is pending at this implementation
commit. These failures are not replaced with a claim that the Work environment
qualified isolation.

## Remaining research work

A1 remains partial: execute the real pretrained baselines on qualified hardware,
then analyze failure modes and sample-size requirements before final test sealing.
Broader missing-cause/model construction and real-language/temporal Augnes
transfer remain open. A2 actual update/adapter save-reload, controlled repeated
training, device/quantization measurements and Augnes adoption are NOT RUN.
No historical paid permit, controller or watcher is changed or reactivated.

The implementation follows the inspected local Bubblewrap 0.9.0 help and
[upstream namespace/mount guidance](https://github.com/containers/bubblewrap),
read 2026-10-26 UTC. Documentation is design guidance; actual boundary outcomes
come from the native probes, not the package's description.
