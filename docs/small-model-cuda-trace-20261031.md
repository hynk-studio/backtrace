# Continue to model evidence: record the denied CUDA operation

The owner's renewed instruction is to continue to the small-model/Augnes
measurement goal and stop only when owner intervention is necessary. Draft #43
is an intermediate result, not completion. Historical results, permits and paid
source/start refs remain unchanged; this branch is stacked on its final head.

The next measurement adds one fourth, fresh hardware-only process D to the
existing A/B/C comparison. It uses the same syscall decisions as C, but records
EPERM denials through a native SIGSYS handler before returning the same errno.
It never executes the blocked call and needs no ptrace permission or extra
capabilities. The original production filter's default remains unchanged.
Clone3's ENOSYS fallback is deliberately not trapped: libc temporarily blocks
signals around pthread creation. An initial local diagnostic reproduced the
resulting SIGSYS termination, and the corrected recorder preserves threads.

Each record contains the syscall number, errno and six integer argument values;
it does not dereference argument pointers. Logs stop after 64 records while
denials continue and the total count is retained. Signal delivery and timing are
different in D, so its result is supplemental evidence, not an unqualified
replacement for C. The collector retains raw streams and partial outcomes.

Reference: [Linux seccomp documentation](https://docs.kernel.org/userspace-api/seccomp_filter.html).
The TRAP action prevents the syscall and reports its number/architecture and
return data in siginfo; the x86-64 handler explicitly restores the error return.

Reuse the existing owner/watcher, authenticated delivery and free exact-image
qualification. The source-bound next permit allows one traced allocation, at
most USD 1 and 3,000 allocation-inclusive seconds, retaining USD 0.50 credit.
No top-up, blind retry, model request or training occurs in this diagnostic.
The new continuation's cumulative spend also stays within USD 1. A supported
correction and subsequent affordable baseline scope follow from the evidence;
finishing this diagnostic is not an instruction to terminate the research task.

Initial local tests verify real socket/fork/exec denial, preserved threads and
clone3 fallback, log truncation, and fail-closed operation without a handler.
The existing root/capability boundary test cannot run in this Work executor
because capability-drop operations are denied; keep that failure and rely on
the required native Linux/container qualification for that boundary. Actual
GPU trace, pretrained E2B responses and Augnes replay remain NOT RUN here.
