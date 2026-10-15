# Kaggle CPU follow-up: restored source and a tested dependency proposal

Observed 2026-10-15 UTC, using source head
`3c05bdae71c7d72c37717972915e48d67a3ed5e6` of Draft PR #7.
Main remained `23616971a4ec57d32fcce769e0a2abf44faa9cfe`; #7 was the only open PR.
The local workspace was a previously blob-verified source snapshot, without a
Git checkout. This follow-up changes documentation/evidence only. It does not
change `docs/source-manifest.json`, production tools, candidate/model/task bytes,
budgets, or the authorized single-allocation envelope.

## Observed progress

The owner-authenticated Kaggle notebook used **Accelerator None**, Linux x86_64,
CPython 3.12.3 for the isolated checks, and the original CPU environment. No model
was mounted or downloaded. All 41 v25 wheels were rehashed successfully. The
previous private result ZIP was restored and verified against its 4,391,742-byte
size and SHA256 `5a2e6c284310a72f1f061589ecb0ba096da59a4a611294f049f0021933876b42`.

That prior result contains the exact 33,461-byte private T4 driver
(`c7eda43a043535eed064b8f347bf271b22eb235c539e44dfe1633c43f47f5189`),
15 of 16 official artifacts, and the frozen 6,230-byte candidate. The preceding
Kaggle run's **80 unit tests passed without skips**; that result is historical,
not a new unit-test run in this documentation-only follow-up.

The official notebook **v2 raw source is now restored**, 14,112 bytes, SHA256
`0c54c3bac3269e422b1d48ac8087ff26b49fe764231b7983c90ef842382f9a87`.
This matches the existing manifest exactly; the executed web-download notebook
and latest v3 source were not substituted.

## Historical notebook retrieval

The failed `version_label='2'` request used the wrong API representation. The
[Kaggle CLI issue and completed fix](https://github.com/Kaggle/kaggle-cli/issues/1200)
document `v<N>` labels. An actual request with Kaggle 2.2.2 / kagglesdk 0.1.37,
`user_name='ryanholbrook'`,
`kernel_slug='getting-started-gemma-4-developer-agent'`, and
`version_label='v2'` returned the exact pinned source in 1.873 seconds.

The acquisition used `ApiGetKernelRequest` and
`client.kernels.kernels_api_client.get_kernel(request)`. It hashed
`response.blob.source.encode('utf-8')` before writing the private file, with no
reserialization or added newline. The source was acquired, not executed. The
SDK operation ran in a bounded owner-side subprocess; authentication values were
not logged or copied into experiment code. The existing public acquisition CLI
still targets the latest-version endpoint and remains fail-closed on drift.

## Why the unchanged v25 runtime cannot resolve

Actual, SHA-verified wheel metadata and bounded resolver runs establish three
independent conflicts:

| Fixed packages | Incompatible requirements |
| --- | --- |
| `google-adk==1.36.1` and `opentelemetry-exporter-otlp==1.44.0` | ADK requires SDK <=1.41.1; the pinned OTLP exporter selects proto-http 1.44.0, requiring SDK >=1.44.0,<1.45.dev0 |
| `xgrammar==0.2.5.post1` and `transformers==5.13.1` | xgrammar requires Transformers >=4.38.0,<5 |
| `google-adk==1.36.1` and `prometheus-fastapi-instrumentator==8.1.0` | ADK requires Starlette >=0.49.1,<1; instrumentator requires >=1,<2 |

Splitting harness and serving environments does not fix the second conflict.
The actual official `VllmServer.build_cmd()` also uses `sys.executable`; its config
has no interpreter override. A split would require an explicit launcher change,
not merely two environment directories. Changing only the OTLP exporter leaves
the Starlette conflict. No metadata, official Python implementation, resolver
requirement, or `pip check` result was patched or suppressed.

## Concrete three-package proposal

The following **proposal only** was resolved, hash-installed and checked in a
fresh disposable CPU environment. It preserves the other **38 v25 wheel files**,
the five official harness packages, vLLM 0.19.1, Torch 2.10.0+cu128,
compressed-tensors 0.15.0.1, Transformers 5.13.1 and tokenizers 0.22.2.

| Package | Frozen version | Proposed version |
| --- | --- | --- |
| opentelemetry-exporter-otlp | 1.44.0 | 1.41.1 |
| prometheus-fastapi-instrumentator | 8.1.0 | 7.1.0 |
| xgrammar | 0.2.5.post1 | 0.2.8 |

The 1.41.1 exporter selects its matching SDK family; instrumentator 7.1.0 accepts
Starlette <1; xgrammar 0.2.8 removes the Transformers <5 cap. Actual replacement
wheel names, byte counts and SHA256 values are recorded in
[the evidence JSON](kaggle-cpu-followup-evidence.json). Original v25 identities
remain in the unchanged source manifest. Three replacements are sufficient for
the observed resolver result, not a claim that all possible alternatives were
exhaustively compared.

`uv pip compile --python /usr/bin/python3.12 --only-binary :all:
--extra-index-url https://download.pytorch.org/whl/cu128
--index-strategy unsafe-best-match --generate-hashes` produced a full proposal
lock. The matching `uv pip install --require-hashes --only-binary :all:` installed
245 packages. PyPI and the official PyTorch cu128 index were used only during
free CPU preparation. The original 38 wheels were direct local references.

| Check | Observed result |
| --- | --- |
| Proposal hash-constrained installation | PASS, 245 packages, 11.828 seconds |
| `uv pip check` on proposal | PASS, all 245 installed packages compatible |
| Imports of torch, vllm, compressed_tensors, transformers and five official packages | PASS, 43.798 seconds |
| Official installed Python files versus five frozen wheels | PASS, byte-identical |
| Separate harness-only environment | PASS, 170 packages; hash installation, dependency check and imports |
| Actual official lifecycle in that harness environment | 10 PASS, 19.687 seconds; maximum fatal detection 0.606739 seconds; zero owned processes remaining |

The lifecycle uses actual adk-submission 0.2.11 lifecycle/HTTP methods with injected
CPU child payloads. It does not start vLLM or a model. These measurements are
separate from the preceding 10-test result and its 0.659849-second maximum.

**The proposal is not the frozen experiment runtime.** Its transitive Linux
inventory and multi-hash resolver lock are retained privately, not substituted
for the strict single-wheel supplemental lock expected by `tools/linux_runtime.py`.
The complete portable wheel bundle, fully offline installation, and execution on
the pinned PyTorch container digest have not been qualified. Import success on
Kaggle CPU does not prove GPU backend selection, kernel compilation, model memory
fit, health or task behavior. A100 hardware and provider gates remain open.

## README restoration and the three requested checks

The original `HARNESS_README.md` remains missing: 49,356 bytes, SHA256
`3d6e57a13234cb4e783ba24eaab486459af76e0923ea4c6607cd41cc8961bbbb`.
The historical v2 notebook's Input explorer also exposes the current 55,940-byte
file. The inspected competition download request has only competition and file
name fields, with no historical version field. The relevant old private CPU/GPU
output listings and five official wheels did not provide the original README.
No guessed version endpoint or reconstructed text was accepted as the original.

The previous current-file download had SHA256
`445000219b803942c469391ec8b69791a31e9cec2f934738c767e34b5ca0aa1f`.
It was not copied over the pinned artifact or used to change its hash.

The unchanged commands were actually attempted in the new harness environment:

| Stage | Result |
| --- | --- |
| Candidate `official_check.py` | Exit 2, missing pinned artifact |
| `compile_probe.py` | Exit 2, missing pinned artifact |
| `official_server_command.py` | Exit 1, one test error at `expected_candidate()` -> `verify_artifacts()` |

Correction to the earlier status: argv validation also requires the original
README through `expected_candidate()`. Restoring the notebook alone does not
unblock it. None of these failed gates is counted as a candidate/compiler/argv
pass. Existing full-reference verification remains in place.

## Continuation boundary

The [authorized recipe](https://github.com/hynk-studio/backtrace/issues/1#issuecomment-5895260495)
freezes all supplied wheels and prohibits unapproved package upgrades. Therefore
the three substitutions are a concrete CPU-tested amendment for owner review,
not an adopted GPU configuration. No repeated generic GPU approval is needed.

Before execution, the remaining work is to resolve the README provenance gate
(recover the exact original, or explicitly review a reference amendment), adopt
an agreed dependency recipe, build its portable offline closure on the pinned
base, rerun candidate/compiler/argv checks, and qualify the complete A100 private
driver plus provider prerequisites. Neither a documentation update nor the
three-package proposal bypasses those requirements.

No GPU allocation, model start, task run, new attempt marker, payment, submission,
merge or issue closure occurred. The temporary environments/cache were removed.
The evidence archive contains private source/artifact bytes and must not be
committed or publicly redistributed. Only authored analysis, version metadata
and identity hashes are included in this repository.

## Saved result and cleanup

The owner-only [Kaggle version 2 output](https://www.kaggle.com/code/hynk1240/backtrace-pr7-cpu-qualification/output?scriptVersionId=358772534)
was saved as `v2 restored; 245-package proposal validated`, with Quick Save output
enabled. The saved Output viewer was inspected: both `pr7-followup/followup-summary.json`
and `backtrace-pr7-followup-evidence.zip` are present. Quick Save's displayed
runtime is a save operation, not a fresh execution of all notebook cells.

The new private archive is 6,349,512 bytes, SHA256
`f128286f0f2efea8b507060cdf34aba3581e2d4cfca6becaafec780c3f167406`.
It preserves resolver/install/check logs, replacement wheel identities, the
restored original notebook and the private source/artifact snapshot. It does
not contain a complete portable 245-package wheel bundle.

After verifying saved output, the Kaggle CPU session was stopped. The editor
showed `off (run a cell to start)`. No GPU or paid resource was created.
