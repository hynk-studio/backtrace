# R0-clean-v2-one-public-task/A10080-TP1 — proposal, NOT authorized execution

Recommend **one RunPod Secure Cloud on-demand `NVIDIA A100 80GB PCIe`,
EU-RO-1**, full GPU, TP=1. No reservation, spot instance, MIG slice, second
attempt or automatic substitute. This is a new environment, not a controlled
hardware-only comparison with T4. Both previous GPU authorizations remain consumed.

## Quote, account and resource evidence

Primary pages inspected **2026-09-29, 13:00–13:21 UTC** advertise **$1.59/GPU-hour**
for A100 PCIe Secure Cloud, 80GB VRAM, 117GB host RAM and 8 vCPUs:
[SKU](https://www.runpod.io/gpu-models/a100-pcie),
[pricing](https://www.runpod.io/pricing).
EU-RO-1/A100 PCIe appears in the provider's
[datacenter example](https://docs.runpod.io/runpodctl/reference/runpodctl-datacenter).
That is a concrete proposed region/SKU, **not current stock evidence**.

The existing Chrome session reached RunPod sign-in; no inherited RunPod API key
or installed CLI was available. One unauthenticated read-only catalog query
returned HTTP 403. No login/account creation, credential search, payment, asset
upload or resource request was performed. **Account balance, exact live quote,
region stock, host allocation and tax remain unverified.** Stop if the exact
configuration is unavailable; do not silently move regions or choose H100.

Before a later allocation, require a fresh authenticated offer for one full
80GB GPU, at least 8 vCPUs/117GB RAM, **100GB container disk**, zero volume disk,
no network/global volume and CUDA >=12.8.1. Require a Linux x86_64 host driver
**>=570.124.06** as a conservative native-toolkit gate, rather than relying on
CUDA minor-version compatibility for PTX JIT. This is the toolkit-corresponding
driver in [NVIDIA's CUDA 12.8.1 table](https://docs.nvidia.com/cuda/archive/12.8.1/cuda-toolkit-release-notes/index.html).
Actual `nvidia-smi` identity, MIG disabled, memory, driver, SM80, UID switching,
capability dropping and `/proc`/mount isolation must pass on the assigned host
before the one server start. Container permissions are not proven by a catalog.

## Cost and bounded run envelope

Propose a **3,000-second maximum billable duration (50 minutes)** from the
allocation request, including provisioning, image/model transfer, setup,
hashing, compilation, task, optional verification, retrieval and deletion.
This explicitly replaces the Kaggle allocation/setup envelope; task limits do
not change. Allow setup at most **1,200 seconds**, startup at most **1,200 seconds**
within remaining time, stop useful work at **2,700 seconds**, then reserve
300 seconds for cleanup. One start and at most one task; fail-fast terminates
early. No retry after setup/startup/task failure.

| Item | Estimate / ceiling |
| --- | --- |
| Expected consumed time | 25–40 minutes, planning estimate; no rental benchmark |
| Compute | $0.663–$1.060; $1.325 at 50 minutes |
| 100GB container disk | About $0.014/hour; about $0.012 maximum, using 720 hours/month |
| Expected consumption before tax | About **$0.67–$1.07** |
| Maximum modeled consumption before tax | About **$1.34** |
| Proposed all-in consumption ceiling | **$2.00**, including tax/rounding and cleanup margin |
| Wallet funding, separate from consumption | Provider advertises starting with **$10**, non-refundable; actual checkout minimum/tax and existing balance unknown |

[Pod billing](https://docs.runpod.io/pods/pricing) states per-second compute and
container-disk billing and no ingress/egress fee. Conservatively count all cold
provisioning/download time as billable; the inspected pages do not establish a
free setup interval. The console's loading skeleton said “per millisecond,” so
do not use that unquoted UI state to overrule the billing page. Confirm the
actual offer and tax before launch; if total projected charges exceed $2, stop.
The $2 consumption cap is a proposed control budget, not a provider-enforced
wallet spending limit or permission to deposit $10. The
[billing guide](https://docs.runpod.io/accounts-billing/billing) requires at least
one hour of configuration credit to deploy. Keep auto-pay off. No paid registry,
network volume or persistent storage is included.

## Portable image and private inputs

The previous `gcr.io/kaggle-private-byod/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461`
manifest returned **401** without registry credentials. Kaggle sign-in is not
evidence of permission to pull that image on RunPod. Do not depend on it.

Proposed image name: **backtrace-r0-linux-cu128**. Accessible public base:
`pytorch/pytorch:2.10.0-cuda12.8-cudnn9-runtime@sha256:b85566342b86d13a67712e9315d40cdc2dad7f8d86df1aff3831f80835edbcca`.
Anonymous manifest/config retrieval succeeded; config identifies Linux amd64,
Ubuntu 24.04, Python 3.12 paths, Torch 2.10.0 and CUDA build argument 12.8.1.
Only 6.4KB of manifest/config bytes were acquired, **no layers pulled or image
executed**. This is an explicit image/OS delta, not Kaggle-image parity.

The private CPU build recipe is:

1. Start from that digest. Materialize the existing wheelhouse v25's 41 exact
   wheel hashes (880,829,403 bytes), existing task dependency wheels and a
   supplemental **Linux CPython 3.12 dependency lock with hashes**. Keep
   `swegemma==0.2.7`, `adk-submission==0.2.11`, `adk-eval-core==0.1.0`,
   `google-adk==1.36.1`, `google-genai==2.11.0`, `vllm==0.19.1`,
   `torch==2.10.0+cu128`, `compressed-tensors==0.15.0.1`,
   `transformers==5.13.1` and every supplied wheel fixed. Use the existing
   separate task venv/Starlette 0.48.0 dependency strategy.
2. Install the complete Linux lock offline with
   `python3 -m pip install --no-index --require-hashes --find-links=/private/wheels -r /private/linux-runtime.lock`;
   apply the pinned notebook's 41-wheel `--no-deps --force-reinstall` step and
   unchanged serving environment. Provision system `git`, `setpriv`, `ps`, SSH
   transport and build prerequisites in that private CPU build; pin its resulting
   image digest and package inventory. Run `pip check`, import checks, the actual
   candidate CPU checks and disposable-process isolation/cleanup checks before
   renting a GPU. No latest-version resolution during a GPU allocation.
3. **Not yet build-ready:** the base lacks the Kaggle preinstalled dependency
   closure; the supplemental Linux lock and final private image have not been
   built/validated. Docker is unavailable locally. The macOS CPU lock is not a
   substitute. A qualified existing free Linux CPU builder is a prerequisite;
   no paid builder/storage is authorized or costed here. Do not publish a derived
   image containing competition packages. If a private image cannot be delivered
   without extra charges, stop and revise the proposal before allocating.

Model v2's eight pinned files total **23,297,590,856 bytes**; the public-task bundle
is about 222MB, and base-image compressed layers total **4,432,776,135 bytes**.
Budget roughly 29GB cold transfer plus image expansion, caches and scratch within
100GB. These sizes, not measured transfer speed, motivate the 20-minute setup
cap. Privately pre-stage only on existing permitted storage. After later approval,
fetch versioned Kaggle bytes in the owner-controlled acquisition process, check
the retained eight-file/41-wheel/input manifests, then transfer over authenticated
SSH to root-owned paths. Do not mount the full competition dataset. No Kaggle or
RunPod credential enters the image's agent environment or shell-visible files.

Preserve the existing root control / dropped-UID agent boundary and verify it on
the provider. Keep evaluator-only answers and reference artifacts off the Pod
during agent execution; stage optional verification inputs only after every
agent descendant is gone. RunPod's public IP is not permission to expose vLLM:
bind to 127.0.0.1, use SSH only, disable Jupyter/public model ports. Fail closed
if the root/UID/capability/mount/canary checks cannot be reproduced.

## Exact serving delta and stop plan

Frozen: `fastapi_11194`; model
`google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2`; candidate **6,230 bytes**, SHA-256
`2e24495826cb971053439a00d9ad8350471fc0efffa41a54b82082feedaa7358`;
five-field input SHA-256
`6ed92f4e646c17728aa8b9ca433a032d61b6b06827eec463a02c00f331c25d60`.
Prompts, AgentTool, no adapters, 32,768 context, sampling, caching/compaction,
one minute / ten tools / fifty turns / sixty seconds per command stay fixed.

Real pinned-wrapper CPU argv checks pass with **injected** SM80/native-BF16 and
one-GPU results. The unchanged predicate
`torch.cuda.is_bf16_supported(including_emulation=False)` should choose
`bfloat16` on A100; vLLM's explicit dtype mapping selects `torch.bfloat16`.
The wrapper omits its default TP=1 flag. Its generated serving suffix is:

```text
-m vllm.entrypoints.openai.api_server
--model /kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2
--host 127.0.0.1 --port 8000 --max-model-len 32768 --dtype bfloat16
--gpu-memory-utilization 0.9 --enable-auto-tool-choice
--tool-call-parser gemma4 --reasoning-parser gemma4 --disable-custom-all-reduce
```

Keep logical `/kaggle/input` paths on the rental image to avoid alias/path changes.
No adapters are discovered; the wrapper's unchanged conditional adapter flags
remain absent. No eager mode, graph disabling, allocator/NCCL overrides, kernel
retiling, context reduction or quantization conversion. The pinned Gemma4 config
forces **TRITON_ATTN** for heterogeneous 256/512 heads even on A100. WNA16/Marlin
eligibility remains source-based; the actual selected linear backend and memory
fit must be observed. A100's documented 163KiB per-block shared-memory capacity
exceeds the historical 96KiB request, but does not prove that this TP1/BF16 kernel
will compile or fit. See [NVIDIA Ampere guide](https://docs.nvidia.com/cuda/ampere-tuning-guide/).
At TP1, retaining no-custom-all-reduce is not evidence of a tested collective fix.

Use the new startup observer, plus a **provider-side** expiry. The
[GraphQL schema](https://graphql-spec.runpod.io/#definition-PodFindAndDeployOnDemandInput)
exposes `stopAfter` and `terminateAfter` DateTime fields on
`podFindAndDeployOnDemand`: propose UTC `t0+2880s` and `t0+3000s` in the single
allocation request. No local `sleep` or Python timeout substitutes for this.
**Conflict preserved:** CLI docs advertise `--terminate-after`, but inspected
runpodctl commit `4351fca9ec454b1bdc8572aaad5d3e5a61ead0fa`'s GPU create path does
not forward it. No installed CLI was tested; use the schema's direct API path,
not that flag. Provider acceptance/timer persistence remains **NOT RUN**.

Before starting the model, capture the create request/ack and verify the scheduled
stop/delete in the authenticated provider view; if expiry cannot be established,
delete immediately. An independent owner-side controller, with its credentials
outside the Pod, also issues `DELETE https://rest.runpod.io/v1/pods/{id}` on
success/failure or at useful-work expiry, then reads that exact Pod ID and the
account Pod list until deletion is confirmed. Export only private logs/results/
patch first within the reserve; skip optional verification if time is short.
Confirm owned processes gone, Pod absent and billing stopped. Stop alone may
retain billable volume storage; termination removes the proposed container disk,
and no persistent volume is created. Do not touch unrelated resources.
Provider/API outages can defeat timely readback; lack of confirmation is a cleanup
failure, not inferred success or a guaranteed hard financial cap.

**Owner decision for later:** authorize one conditional A10080-TP1 attempt with
a $2 consumption ceiling and 50-minute maximum, only after account sign-in, exact
offer, Linux image qualification and native-expiry prerequisites pass. Any needed
minimum $10 wallet deposit (plus displayed tax) is a separate owner payment
decision. No files need manual preparation and no Kaggle re-enrollment is needed.

Source access times, response/artifact hashes and observed limitations are in
[startup evidence](startup-guard-evidence.json). No GPU/model/provider operation
was executed for this proposal.
