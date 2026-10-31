# E2B first measured baseline and Augnes development replay

The subsequent listener-corrected attempt completed actual inference. Read the
[measured result and retained evidence](small-model-e2b-result-20261031.md).
The failed attempt and preparation chronology below remain historical records.

The first attempt failed before model transfer/inference. A/B passed actual
CUDA kernels; corrected C/D still failed initialization. The new trace identified
two `connect` and two `bind` denials. All 24 assignments remain NOT_RUN. Both
controllers confirmed deletion; the current correction is being qualified.

The executable source is `13f98c34cb90de7d9265af74d8153aecb78b9d1b`, tree
`739f865f7a6e593d3bf22c7dc40b4cb62311da85`. The immutable paid start is
`bt-001-e2b-baseline-start-20261031`; the review branch remains Draft PR #45.
Run [41203845196](https://github.com/hynk-studio/backtrace/actions/runs/41203845196)
uses one fresh authorization in `e2b-baseline-paid-20261031`. Neither historical
diagnostic permission nor a prior resource is reused.

## Exact-source free qualification

Run [41202852503](https://github.com/hynk-studio/backtrace/actions/runs/41202852503)
passed on attempt 1 before allocation. Its complete native Linux suite passed
688 tests in 208.633 seconds. All 17 ordinary-container controls passed; the
actual pretrained entry explicitly rejected a missing GPU instead of using CPU
inference. Independent free cleanup observed absence twice. Local Work execution
retained 7 failures, 10 errors and 4 skips under its restricted kernel; these were
not relabelled as native passes.

The pinned tokenizer reproduced all original 18 E2B inputs and all six new replay
inputs before allocation. The original denominator is nine views of one
development episode, not nine independent episodes. The additional replay
denominator is three distinct historical development episodes, each under B0/B1.
The author knew historical outcomes; no held-out or prospective claim is intended.
The #1549 reference is a real engineering commission, not a completed-fix result.

Verified free artifacts:

| Artifact | SHA-256 |
| --- | --- |
| Container 13043456181 | `8ae375b1e380ebfee65a79e47b929a8648e13bd72f95765a0f56c39d4a2d6bb1` |
| Input/checkpoint 13042524880 | `af0b28c6aa3e15c0f94f0638bb4d9bd0a0a0aa65df6f9a5f12b5501b1c860785` |
| Free owner 13043630056 | `973697c14700eed2851c7b800ef4076fe247a28dd21afa6b4b9e456ab37a4628` |

## Actual scope

The fresh read observed USD 2.8022904793 with no resources, zero hourly spend and
autopay off. One A40 in CA-MTL-1 was allocated as `uj3llp7bzrc70k`.
The fresh quote projected at most USD 0.5041666667 for all 3,000 seconds, including
storage. This is a ceiling projection, not measured final billing. The prior
trace in this continuation consumed an observed USD 0.1037536546.

The first comparison applies the narrow socket correction supported by the
[retained denied-call trace](small-model-cuda-trace-result-20261031.json).
Actual A/B/C/D, the complete hardware and active-interruption controls, model
transfer/loading, original outputs, replay outputs and independent deletion are
separate observations. A success in one does not establish success in the next.
The full model remains a bounded ordinary-container attempt: provider/visible
memory can be observed, but hidden host memory ancestry is not attested.

The bound is 24 requests, 1,500 collection seconds, 180 startup seconds and
90 seconds per request, with no training, E4B inference or production adoption.
All original failed, missing, invalid and truncated outcomes remain in their
assigned denominators. The rubric is frozen separately from the model inputs.

## Actual outcome and next correction

The [retained original evidence](small-model-e2b-first-attempt-20261031.json)
includes all comparison streams, all assigned input identities, source/member
hashes and cleanup receipts. A/B passed BF16 matmul and SDPA. C/D returned CUDA
304. D recorded syscall 42 twice and syscall 49 twice, without truncation or
abnormal exit. No model weights were transferred to the provider, and no request
was generated. The original coarse classifier is retained unchanged.

The previous socket-creation-only correction was insufficient. The new candidate
adds only `bind` and `listen` for the one possible socket shape. An upstream
[snapd CUDA investigation](https://forum.snapcraft.io/t/problem-with-confined-nvenc-cuda-ffmpeg-snap/5183)
observed a CUDA UVM abstract socket requiring bind/listen and reported confined
CUDA execution after that change. This is supporting evidence for a candidate,
not proof that our current driver has the same requirement or that `connect`
denial is harmless. The current trace did not copy socket address memory.

The classic BPF filter does not constrain socket address strings. It constrains
socket creation to AF_UNIX / SOCK_SEQPACKET|SOCK_CLOEXEC / protocol 0 and denies
connect, both accept variants, sendmsg, sendto and socketpair. No socket is
inherited. A passive peer may queue a connection, but the worker cannot accept
it or read it through the listening descriptor. The real kernel regression uses
an unfiltered parent peer to test this condition. Other network socket families
and types, process/exec/namespace changes and credential access remain denied.

Owner deletion finished at 13:22:15 UTC; the watcher finished at 13:21:03 UTC.
Each independently observed absence twice. The account read at 13:22:16 UTC and
complete inventory at 13:22:25 UTC found USD 2.7145033478, zero spend, zero Pods
and autopay off. Observed decrease was USD 0.0877871315 for this attempt and
USD 0.1915407861 for this continuation; these are observations, not final billing.
Owner artifact 13044547415 has SHA-256
`f1fa87f0f90aaf24fe384fb3d093ca0adf3f95f21ed296ab6386578b5cdb088c`;
watch artifact 13043388063 has SHA-256
`f119d4a613a242ab445a16950c66007bfedf39234999acf3dc38811b432239ed`.

The next supported attempt uses `e2b-listener-paid-20261031` and the new immutable
start `bt-001-e2b-listener-start-20261031`, only after complete free qualification.
It preserves the original 24 assignments and still compares A/B/C/D before model
work on the same allocation. The consumed first source/start/permit stays fixed.
No pretrained result or Augnes utility is established; continue to measurement.

The first passive-listener free run, 41205794481 at
`60b2f79173925f01ae896f24175e610e611d3636`, failed one of 688 native tests:
the new test attempted to JSON-encode Python's bytes-valued abstract Unix socket
address. Socket creation/bind/listen had already succeeded. Explicit ASCII
decoding fixes the test's parent/child address handoff; the production filter is
unchanged by that correction. Preserve artifact 13044049582, SHA-256
`1c28353ed08885bb8637b5f85c63450031a1dca4dc5fc1f07b59ce3d0690ed82`.
No new paid action occurred. Complete native/container qualification is still
required before the next permit.
