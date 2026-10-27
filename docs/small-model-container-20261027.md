# Ordinary-container execution correction (2026-10-27 KST)

The prior exact-image test passed transport but could not create nested
namespaces. This version keeps the original collector, evaluator, labels and
development scope on the native owner. A dedicated ordinary OCI container
receives only an authenticated, hash-bound Python/runtime bundle, fixed worker,
public tokenizer metadata, tiny random CPU checkpoints and input frames. No
provider credential or evaluator repository enters it. Authored response IDs
are sent only to the explicitly labelled qualification control.

The unchanged image is
`pytorch/pytorch:2.10.0-cuda12.8-cudnn9-runtime@sha256:b85566342b86d13a67712e9315d40cdc2dad7f8d86df1aff3831f80835edbcca`.
Its system Python remains a stdlib bootstrap. A manifest-bound copy of the
owner's pinned Python 3.12.14 is installed in a separate prefix, followed by the
unchanged 56-wheel CUDA 12.6 closure with hashes, no index and no dependencies
resolved during install. Installed package equality, native-library resolution
and CPU tensors are checked inside the image. This is not GPU execution.

The trusted root supervisor serializes work, drops all bounding/effective
capabilities and supplementary groups, and executes the unchanged worker as
UID/GID 65532. The x86_64 seccomp filter denies sockets, exec, non-thread clone,
fork, ptrace, cross-process memory and namespace changes. Python threads remain
available. The container's outer PID/network namespaces separate the owner;
root-owned runtime/assets are non-writable by the worker, and root's SSH
material is unreadable. This is a new dedicated-container boundary, not a claim
that the original empty-mount-tree bwrap boundary now works inside a container.
It must not be reused as a multi-tenant service or a tool-executing coding agent.

The supervisor relays bounded stdin, kills/reaps the worker on transport EOF or
deadline and establishes a parent-death signal after changing UID. The filter
forbids process descendants, reducing teardown to the one worker and its
threads. Qualification separately kills the local SSH transport and remote
privileged supervisor, observes remote PID/start identities, then removes the
whole owned container with two absence reads. The owner collection deadline
and all original missing-execution accounting remain unchanged.

Free native qualification is pending at this source. It must pass the complete
suite, pinned runtime installation, enforced boundary controls, 36 authored
assignments with exact answers, 36 tiny-random diagnostic assignments, startup
hang/hang/crash/wrong-ID/oversize controls, transport loss and supervisor loss.
These are one selected family/episode with nine views, two arms and two model
tokenizers, not 36 independent capabilities. No pretrained capability claim is
possible from these controls.

Paid launch remains disabled in both code and workflow. The adapter rejects
pretrained and CUDA execution modes. Container cgroup roots hide ancestors:
the original strict native memory reader is preserved. The free replica has
an explicit host-enforced 6 GiB quota; this does not establish the provider's
8/32 GiB headroom requirements. Live provider memory admission, network/NAT,
actual GPU/context teardown, and a source/resource-bound independent deletion
controller remain separate launch gates. No old permission is reset.

Primary API rationale inspected 2026-10-27: Linux
[seccomp BPF](https://docs.kernel.org/userspace-api/seccomp_filter.html) and
[Docker default container capabilities](https://docs.docker.com/engine/containers/run/).
Observed execution, source hashes and retained failed attempts will be recorded
in a separate receipt after the native run completes.
