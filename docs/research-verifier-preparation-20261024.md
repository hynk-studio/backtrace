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
no-new-privileges. Local test servers may use sandbox loopback; a disconnected dummy device drops
outgoing packets so actual TCP connect-timeout tests retain their behavior; host gateway and
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

The CPU qualification loop has an independent 1,800-second deadline; exhausted
remaining cases are explicitly NOT_RUN. The 40-minute workflow bounds acquisition
and export as well. The new workflow records all six verifier pairs and all 18 isolated authored
runner fixtures. Public records contain counts, identities and checks; raw test
outputs and task material leave the host only encrypted to the existing owner
recipient. The original acquisition, runtime and runner evidence remains intact.

Initial actual run 40095255162 at e2c383470ee659974d1eb97a962e4f3acf1c7883
found three valid verifier pairs and three failures. Its full public receipt is
retained in `research-verifier-boundary-cpu-20261024.json`. The timeout probe
correctly rejected a command that never reached its marker; namespace entry had
changed the working directory. Explicitly restoring the workspace also corrects
the authored runner marker failures. The HTTPX editable backend needs the real
`editables` package. Four Requests timeout tests received network-unreachable
errors with loopback alone; the isolated sink uses genuine kernel TCP timeout
behavior without any external connection.

Rich `rich_3486` reveals a separate upstream verifier incompatibility. Its original
test patch adds complementary pre-3.11 and 3.11+ tests, each with its original
version skip. The official JUnit validator requires both added test names to pass.
On the frozen Python 3.12, actual pytest succeeds but the official verifier rejects
the intentionally skipped pre-3.11 test. Changing Python would skip the other
branch. Do not remove the skip, forge a passing test, weaken the original checker,
replace the selected task, or report this as a model failure. This selected slot
remains an explicit qualification blocker pending an agreed verifier/protocol
amendment. The original official verdict is preserved.

Earlier workflow parse failure 40094720185 ran no job. Run 40094763688 passed the
Linux suite but could not export root-owned receipts. Run 40094967033 retained
its failed dependency-acquisition evidence: the exact downloader required a
private directory. That directory and artifact ownership were corrected; the
minimal CPU runtime uses its pinned pip wheel for offline overlay installation.
Further executed results will be recorded after the corrected workflow completes.
Remaining gates include full GPU image/model/cache identity and a finite 18-run
cost/lifecycle proposal. No allocation, training, merge, issue closure or
competition submission is authorized by this preparation.
