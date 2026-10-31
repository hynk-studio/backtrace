/* Diagnostic-only x86-64 SIGSYS recorder. The denied syscall never executes.
 * Return the original EPERM/ENOSYS after logging at most 64 records. No ptrace,
 * extra capabilities, allocation, stdio, or pointer dereference in the handler.
 * https://docs.kernel.org/userspace-api/seccomp_filter.html
 */
#define _GNU_SOURCE
#include <errno.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdint.h>
#include <ucontext.h>
#include <unistd.h>

#ifndef SYS_SECCOMP
#define SYS_SECCOMP 1 /* Linux UAPI asm-generic/siginfo.h */
#endif

#if !defined(__x86_64__) || ATOMIC_INT_LOCK_FREE != 2
#error "Linux x86-64 with lock-free unsigned counters required"
#endif

static _Atomic unsigned count;

static char *literal(char *p, const char *s) {
    while (*s) *p++ = *s++;
    return p;
}

static char *number(char *p, uint64_t n) {
    char digits[20]; unsigned k = 0;
    do { digits[k++] = (char)('0' + n % 10); n /= 10; } while (n);
    while (k) *p++ = digits[--k];
    return p;
}

static void denied(int sig, siginfo_t *info, void *context) {
    ucontext_t *u = context;
    if (sig != SIGSYS || info->si_code != SYS_SECCOMP ||
        info->si_arch != 0xc000003eU ||
        (info->si_errno != EPERM && info->si_errno != ENOSYS)) _exit(159);
    /* No allocation and one bounded write, including from CUDA helper threads. */
    unsigned index = atomic_fetch_add_explicit(&count, 1, memory_order_relaxed);
    if (index < 64) {
        char line[512], *p = line;
        const int regs[] = {REG_RDI, REG_RSI, REG_RDX, REG_R10, REG_R8, REG_R9};
        p = literal(p, "BACKTRACE_SECCOMP_DENIAL {\"syscall\":");
        p = number(p, (unsigned)info->si_syscall);
        p = literal(p, ",\"errno\":"); p = number(p, (unsigned)info->si_errno);
        p = literal(p, ",\"args\":[");
        for (unsigned i = 0; i < 6; ++i) {
            if (i) *p++ = ',';
            p = number(p, (uint64_t)u->uc_mcontext.gregs[regs[i]]);
        }
        p = literal(p, "]}\n");
        ssize_t ignored = write(STDERR_FILENO, line, (size_t)(p - line));
        (void)ignored;
    }
    u->uc_mcontext.gregs[REG_RAX] = -info->si_errno;
}

int backtrace_trace_install(void) {
    struct sigaction action = {0};
    action.sa_sigaction = denied;
    action.sa_flags = SA_SIGINFO;
    if (sigemptyset(&action.sa_mask) || sigaction(SIGSYS, &action, 0)) return -1;
    sigset_t unblock;
    if (sigemptyset(&unblock) || sigaddset(&unblock, SIGSYS)) return -1;
    return sigprocmask(SIG_UNBLOCK, &unblock, 0);
}

unsigned backtrace_trace_count(void) {
    return atomic_load_explicit(&count, memory_order_relaxed);
}
