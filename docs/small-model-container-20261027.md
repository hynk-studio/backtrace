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
whole owned container with two absence reads. The original collector deadline
logic and missing-execution accounting remain unchanged; transport close has a
separate bounded exit allowance. Owner and Docker replica share one native
runner/kernel: loopback SSH disruption is not live provider NAT or cross-host
resilience evidence.

Native run [40445252781](https://github.com/hynk-studio/backtrace/actions/runs/40445252781)
at `eef423182e449d94cd3118a721f914881366901a` passed all 639 tests in 172.176 seconds
with no failures, errors or skips, CPU preflight and all 23 connected
container checks. Both 36-assignment controls completed: authored answers had
zero loss; tiny random outputs were INVALID_OUTPUT and match the earlier native
CUDA-build CPU outputs exactly. All preparation bytes and tiny checkpoint bytes
also match the earlier qualification. Startup hang, request hang, crash,
wrong-ID, oversize, remote deadline, actual SSH loss and privileged supervisor
loss were exercised. The owned container was then confirmed absent twice.

Read the [verified evidence](small-model-container-evidence-20261027.json).
All 207 members across 6
new artifacts and all 47 operational source hashes were checked. The earlier
109-member native CUDA CPU artifact was independently checked for parity.
All 41 prior operational sources and 75 previous branch heads remain unchanged.
The local Work suite ran 639 tests in 139.331s with five failures, ten errors and
four skips in the existing ensurepip/procfs/native-host paths; its full diagnostic
section and the first truncated local attempt remain recorded separately.
Seven focused local tests passed. Native qualification is the complete execution
evidence; local environment failures are not relabelled as passes.

Five earlier failed native runs remain retained. The first lacked controller
HTTP dependencies in the exact model environment; the second installed the
wheels but rejected the relocated interpreter. The correction binds and checks
`/opt/backtrace/python/lib/libpython3.12.so.1.0`, rather than trusting version
selection alone. Two already submitted versions stopped on a create-only receipt
write conflict after the authored control; their final cleanup results were not
retained and are not claimed. Append-only checkpoints now preserve progress and
permit one final receipt. A later run rejected a startup-fault request timeout
larger than its one-second total budget; the diagnostic configuration now obeys
the unchanged collector contract. No paid request was made in any attempt.

The 36 assignments represent one selected family/episode with nine views, two
arms and two model tokenizers, not 36 independent capabilities. No pretrained
capability claim is possible from these controls.

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
Observed execution, source hashes and retained failed attempts are recorded
in the verified evidence receipt linked above.

The native Python builder's absolute library search path was inspected in
[actions/python-versions](https://github.com/actions/python-versions/blob/main/builders/ubuntu-python-builder.psm1).
The exact previously loaded wrong Python version was not retained in the failed
attempt; the corrected loaded-library identity and Python 3.12.14 are observed
in the successful run. The transport exit allowance also exceeds the remote
one-second graceful worker shutdown, avoiding equal-deadline close races.
