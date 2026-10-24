# Selected verifier and isolation preparation — 2026-10-24

Continues #1 and Draft #22 on `bt-001-research-verifier-prep-20261024`.
This is free CPU qualification. All 18 real-model slots remain NOT RUN.

The six selected tasks, three archives, prompts and matched protocol stay fixed.
Each task receives two fresh official verifier executions: an unmodified baseline
and its original public reference patch. Only the root coordinator reads original
metadata; the reference patch enters only the positive control. Results require
actual JUnit, executed tests, matching pass/fail exit status and a verified import
from that sandbox's source checkout. Collection/setup errors remain infrastructure
failures, never unresolved model scores. The subprocess verifier skips package
installation; this wrapper performs an offline editable install as the evaluator
UID before the original test command. The separate evaluator dependency lock
adds no packages to the 143-package agent runtime.

Model-selected commands run as UID 65532, verifier commands as UID 65533. Trusted
coordinators, reference data and HTTP accounting remain root-owned. Every sandbox
has its own PID, network and proc-mount namespaces, dropped capabilities and
no-new-privileges. Local test servers may use sandbox loopback; host gateway and
upstream loopback are unreachable from commands. File-copy tools refuse symlinks,
hardlinks and special files through descriptor-relative operations. These are
specific boundaries on a disposable Linux host, not a complete hostile-host
filesystem jail or a qualified GPU deployment image.

A timer begins at the official agent-session timestamp and terminates the PID
namespace when the 300-second allowance ends. Command timeouts cannot exceed the
remaining allowance. An independent 330-second child PID namespace bounds setup,
execution and cleanup, including detached descendants. Qualification uses actual
official command execution and deliberately shortened 0.5-second controls to
observe expiration without consuming five minutes per regression.

The new workflow records all six verifier pairs and all 18 isolated authored
runner fixtures. Public records contain counts, identities and checks; raw test
outputs and task material leave the host only encrypted to the existing owner
recipient. The original acquisition, runtime and runner evidence remains intact.

Execution results will be recorded after the actual Linux workflow completes.
Remaining gates include full GPU image/model/cache identity and a finite 18-run
cost/lifecycle proposal. No allocation, training, merge, issue closure or
competition submission is authorized by this preparation.
