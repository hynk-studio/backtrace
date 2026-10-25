# Split inference qualification

Draft #25, stacked on #24. This change prepares a native Linux CPU coordinator
for original isolated tools and separate evaluation. A mutually pinned TLS 1.3
forwarder in the frozen inference image exposes only bounded chat completions.
The root coordinator owns the client key; agent commands retain separate UIDs,
PID/network namespaces and the original command/work/request limits.

The frozen v2 protocol, six tasks, balanced 18-slot order, candidate prompts,
checkpoint/image and v3 evaluator rule are unchanged. Prior paid scopes remain
consumed. This code cannot allocate a provider instance or mint a launch permit.

## Operational behavior

- The existing request ledger admits each HTTP attempt before TLS connection,
  including root/delegate, retries and compaction. Missing token usage stays
  unknown. Rejected or interrupted connections do not create extra reasoning time.
- The remote forwarder pins both certificate leaves, accepts only the chat route,
  bounds body/response/remaining time, cancels a stalled upstream on disconnect,
  and has a finite lifetime. The model HTTP listener remains loopback-only.
- Each slot gets a new official context/cache, candidate and workspace. The fixed
  sequence reserves a full 330-second child plus 360 seconds export and 300 seconds
  cleanup before admission; remaining slots stay NOT_RUN if admission fails.
- The original submit_patch acknowledgement atomically checkpoints its exact
  patch. After a work deadline the submitted artifact survives. An outer kill may
  leave only that checkpoint and partial accounting; no final trace or token
  totals are invented. An unsubmitted diff after isolation stops is unavailable.
- The official server command builder receives --no-enable-prefix-caching. A new
  loopback metadata middleware requires the initialized engine's prefix cache to
  be exactly False along with the frozen dtype/context/parallel settings.

## Evidence scope

Source-read run [40160733853](https://github.com/hynk-studio/backtrace/actions/runs/40160733853)
verified the 433,132,506-byte v25 vLLM wheel, SHA256
6b29fdc200966eda4d0cc4d10b8c338ec32620bb069ad3629d8a78e3b35fd3fa.
Its actual BooleanOptionalAction registration maps omitted/enable/disable to
None/True/False. The narrow pinned parser slice is executed independently; no
claim is made that a GPU engine was initialized. Run 40160571189 failed YAML
parsing before any job and was corrected without a paid operation.

Full free qualification is pending. Its topology is native isolated official
runner -> TLS forwarder in the exact image -> native authored HTTP responder.
The container uses host networking to reach that test responder, drops every
capability, has a read-only root and no task/evaluator mount or client private key.
The same forwarder persists across all 18 task/arm fixtures. These authored CPU
responses exercise plumbing, not task solving or GPU cache effectiveness.

The suite also runs retry/compaction, real original submit_patch before/after
scaled work deadline, outer-child kill, isolation controls, wrong/no certificate,
stream/JSON request counting and cleanup. Private patches, traces and logs are
owner-encrypted. Public receipts contain identities, counts, states and hashes.

## Remaining gate

A provider-ready immutable launch namespace, authenticated delivery/start of the
new server-only command, initialized GPU cache/model readiness and provider
network/deletion behavior remain separate integration/authorization work. No
provider allocation, model-file transfer, GPU run or Kaggle submission occurred.
The three-hour/USD6 proposal remains blocked and is not permission to spend.
