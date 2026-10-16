# Approved three-package runtime amendment

On 2026-10-16 UTC the owner approved the exact three substitutions proposed after
PR #7 head `9e2dae734854a563336f41b1410789a292c70f8d`. This adopts that change in
the execution recipe; it does not authorize additional package changes or alter
the existing conditional single A100 attempt, $2/3,000-second envelope, model,
task, candidate, prompts, serving settings or evaluator separation.

| Package | Historical v25 | Approved runtime |
| --- | --- | --- |
| opentelemetry-exporter-otlp | 1.44.0 | 1.41.1 |
| prometheus-fastapi-instrumentator | 8.1.0 | 7.1.0 |
| xgrammar | 0.2.5.post1 | 0.2.8 |

The exact original/replacement wheel filenames, byte counts and SHA256 hashes
are in [a100-runtime-amendment.json](a100-runtime-amendment.json). Replacement
identities were acquired and tested in the preceding private Kaggle CPU run.
The other 38 supplied wheels remain byte-identical. There are 41 selected
runtime wheels totaling 833,990,706 bytes; this is not the complete transitive
dependency bundle.

The historical `docs/source-manifest.json` is unchanged, SHA256
`873e9dc7cf372948c154fb6b9d1e24170f1eb74fea4426d32fc17702581a030a`.
The amendment JSON is SHA256
`24baa8489b5cdfef9f135b195db78ec856df8cffd61ae4696da11e71ef52fdc6`.
The five official harness packages, vLLM 0.19.1, Torch 2.10.0+cu128,
compressed-tensors 0.15.0.1 and Transformers 5.13.1 retain their existing pins.

## Installation behavior

`tools/linux_runtime.py` now derives its selected wheel list from the original
v25 inventory plus this approved amendment. It rejects a changed source manifest,
wrong original identity, missing/extra/duplicate substitution, unexpected version
or invalid replacement identity. It verifies all selected wheel bytes before
creating an environment. A supplemental lock cannot override these pins or
bring back one of the three superseded versions.

The same amended selection is used for both dependency installation and the
subsequent `--no-deps --force-reinstall` stage. That second stage previously
reinstalled all original v25 packages and would have undone the approved change.
It now reads `runtime-pins.lock`. The output also contains the full combined
`linux-runtime.lock`, a copy of the exact `runtime-profile.json`, and package
inventory; the success receipt includes the profile and lock SHA256 values.
Network denial, hash requirements, frozen core versions, import/dependency
checks, refusal to overwrite outputs, and rollback on failure remain in place.

With the selected wheels, complete transitive wheel bundle and strict Linux
supplemental lock privately available, the existing invocation is unchanged:

```sh
python3 tools/linux_runtime.py .local/linux-wheels .local/linux-supplemental.lock .local/linux-runtime
```

Use this on the pinned PyTorch base before allocation. It performs no online
resolution. The old private multi-hash proposal lock is diagnostic evidence;
it is not a substitute for the installer's one-selected-wheel-per-row lock.

## Evidence and remaining work

The preceding [Kaggle report](kaggle-cpu-followup.md) records successful online
hash installation, dependency checking and imports for 245 proposal packages,
and 10 actual-wrapper lifecycle checks in a separate 170-package harness.
Those results are historical and are not reruns of this implementation.

New validation on 2026-10-16:

| Check | Observed result |
| --- | --- |
| Focused runtime tests in Cloud, Python 3.12.14 | 9 PASS, 8.248 seconds |
| Full suite in Cloud | 83 run: 74 PASS, 1 failure, 8 errors; 16.447 seconds |
| Same 28 source/config files in Kaggle CPU, Python 3.12.14 | **83 PASS, 0 skipped**, 20.829 seconds |
| Kaggle authored lifecycle cases within that suite | 9 PASS; fatal detection max 0.046982 seconds; zero owned processes remaining |
| Preflight in Cloud and Kaggle | `local_tooling: READY`; official validator NOT RUN |
| Changed Python syntax, whitespace and source-manifest identity | PASS |

Cloud's `/bin/ps -axo pid=,pgid=,stat=` also failed standalone with exit 1 and
`fatal library error, lookup self`. Eight lifecycle errors came from that call;
the other failure was a residual-PID assertion. An earlier Cloud invocation
ended without a unittest summary and is not counted as a completed suite.
No matching live task fixture processes were found afterward. The original
Cloud failures are retained, not relabeled as passes. Kaggle's `ps` worked,
and all 28 transferred source/config hashes matched the local files before
accepting its full-suite result. Production startup/cleanup code was unchanged.

The new real offline pip fixture places both old and replacement wheels in the
same directory, then verifies that hash installation, force-reinstall, dependency
check and final inventory retain the replacement. These are authored tiny wheels;
their success does not qualify the complete official dependency closure.
Private logs and source hashes are summarized in
[a100-runtime-amendment-evidence.json](a100-runtime-amendment-evidence.json).
The temporary Kaggle test interpreter and cache were removed after the tests.

The [private Kaggle version 3 output](https://www.kaggle.com/code/hynk1240/backtrace-pr7-cpu-qualification/output?scriptVersionId=358884071)
was saved as `Approved pins; 83 CPU tests passed`, using Quick Save with output.
The saved viewer contains `pr7-amendment/summary.json`, `tests.log` and
`preflight.json`, plus the tested source files. The editor then confirmed
`off (run a cell to start)`. Quick Save's displayed runtime is not another test run.

This amendment does not supply the missing original `HARNESS_README.md` or relax
the candidate/compiler/argv artifact gates. A complete portable offline bundle,
offline qualification on the pinned base, actual A100 driver qualification and
provider prerequisites remain outstanding. No GPU/model/task/submission was
started while adopting these pins.
