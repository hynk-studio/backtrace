# Inference-only delivery and lifecycle rehearsal

Status: implementation under free CPU qualification, not a paid launch gate.
Stacked on Draft #25, related to #1. All real-model comparison slots remain
NOT_RUN. No historical paid authorization, state claim or branch is reused.

The serving bundle contains an explicit list of server/bootstrap modules, the
unchanged 246-wheel inventory and three server-side TLS files. It excludes the
task compiler, task archives, evaluator inputs and the client private key.
The frozen image receives this bundle over mutually authenticated bootstrap TLS
and pinned SSH, then downloads the exact wheels using scoped URLs and installs
them offline. The official server command is constructed in that environment.

One process owner supervises readiness, TLS forwarding, signals, lifetime and
server process-group cleanup. Model mode requires the exact eight-file weights
and CUDA hardware; free qualification instead uses an explicitly authored CPU
process. Authored readiness cannot satisfy the model metadata check. The relay
is reached through Docker bridge port publication, with no host mounts. This
is not an observation of a provider's network or initialized GPU engine.

The independent watcher uses a fresh create-only CPU rehearsal namespace. It
binds cleanup to the exact container name, label and observed ID, and requires
two successful absence reads. Owner completion, heartbeat loss, state failure
and total deadline trigger cleanup. The qualifier joins all 18 fixed isolated
slots to serving, encrypted export and both owner/watcher cleanup observations.
Failed readiness, parent death, bridge disconnection and insufficient remaining
time are explicit free controls. Errors cannot be counted as absence and an
insufficient window preserves every NOT_RUN slot.

The local journal and Docker adapter are CPU replicas. The fresh distributed
GitHub/Runpod owner/watch entry, quote/account validation and finite paid claim
still require a separate source-bound integration and explicit authorization.
No provider create API or paid entry is added by this rehearsal.

Validation results will be recorded after actual native Linux execution; source
inspection and unit tests alone do not establish full-image qualification.
