# Actions controller migration

The owner accepted the cloud-browser/Actions/RunPod proposal at 20:31:26 KST
on 2026-10-19. The new policy is `a100-cloud-policy.json`: setup up to 90 minutes,
allocation through confirmed deletion up to two hours, one further allocation,
server start and public task at most, within the existing USD 10 wallet and
USD 8 cumulative stop. The prior CA-MTL-3 attempt remains consumed and deleted.

## Current result

The later 19:57 KST browser queue request found actual matching CA-MTL-3 stock.
The already-approved single further attempt ran at source
`91788995fa6e7fd185a4a4e001a13558ce37581b`. All input delivery, offline runtime,
actual isolation and model file hashes passed. The server child then failed
before model startup because the pinned runtime image has no developer toolkit
version manifest. Owner and independent watcher confirmed Pod deletion; a fresh
complete list found zero Pods, USD 9.1617621462 balance and zero hourly spend.
The authorization is consumed. See [the latest execution record](a100-execution-20261020-1957.md).

The runtime version correction passed actual cudart observation, all 251 CPU
tests and full free qualification at source
`0dc0bb6088a9ea5f872110ca7daecf0cf6b63820`. No new paid allocation is authorized. The scientific driver, model,
prompts, candidate, TP1 BF16 and experimental budget remain frozen.

## Earlier readiness record (historical)

Update 2026-10-20: a fresh exact offer and all free gates passed at source
`8fc553912ed1a7262793ccfce21ef50702516e97`. The dedicated owner run
39369857734 then found no stock in any region at its final read, before claim
or create. Allocation requests, new Pods and new spending were all zero.
The watcher/start branches are now activated historical runs, not unused triggers.
The claim remains absent. See [the current execution record](a100-execution-20261020.md)
and [the nullable quote compatibility evidence](a100-offer-compatibility.md).
The subsequent free-watcher handover change preserves the claim and requires
the previous watcher to be terminal before replacing its unused lease.
Latest qualified launch source: `80cb0efa905ba7f068ea10e04ecf1c37c4382401`;
244/244 full CPU tests and actual owner preflight passed. Its 04:40:01Z read
again found no matching offer, unchanged balance and zero spend. The next
actual watcher must establish its own fresh lease before a paid claim.

The following is the retained 2026-10-19 readiness record:

Free input/runtime/wrapper qualification and the real owner preflight passed.
The qualified launch source is `b2b2ad290aae0967559e0cf14002672d32c05584`.
Full CPU suite: **235/235**, 27.223 seconds, preflight READY and successful
workflow conclusion. Real owner run:
https://github.com/hynk-studio/backtrace/actions/runs/39289474231
Its 5,578-byte create body is below the 102,400-byte provider limit; no create
was sent. Pinned transport, fresh identities, all scoped source maps and the
unused durable claim passed their actual preflight checks.

At 2026-10-19T16:57:39Z the account had USD 9.8508333333 credit, zero spend rate
and Auto-Pay disabled. There was no qualified regional A100 offer. A separate
complete list at 16:54:21Z contained zero Pods. No watcher/start branch has been
activated. A new live matching offer is required before the already-authorized
single paid attempt; no funding or approval reset is required.

## Earlier migration observations (historical)

- The public Draft PR remains #7 on `bt-001-a100-cpu-qualification`; main is untouched.
- First Actions run: https://github.com/hynk-studio/backtrace/actions/runs/39246227301
- Source: `65a6a4f539929fcaaee23be98ef55bd54a9c8606`.
- Ubuntu 24.04, qualified Python 3.12.14, actual root Linux PID namespace check.
- **169/169 existing tests passed in 25.247 seconds**, preflight READY.
- Secret-free CPU log artifact retained for seven days; no private inputs uploaded.
- New component tests: 25/25 passed locally, then **194/194 total tests passed in
  23.669 seconds on Actions**, including the new components. Preflight READY.
  Run: https://github.com/hynk-studio/backtrace/actions/runs/39247485067
  Source: `1c7bfacb4dc2cc5a7f936bae4e2388315282084d`.
  These use synthetic HTTP/provider fixtures; they do not establish live storage
  throughput or paid cancellation. See `a100-cloud-cpu-evidence.json`.
- The owner registered `RUNPOD_API_KEY` and `KAGGLE_API_TOKEN` as Actions Secrets.
  Authenticated read-only checks passed against RunPod and the frozen Kaggle
  model v2, private selected-task v1 and retained private notebook v3.
  Run: https://github.com/hynk-studio/backtrace/actions/runs/39276929758
- Latest completed CPU suite: **235/235**, 27.223 seconds, preflight READY.
  Run: https://github.com/hynk-studio/backtrace/actions/runs/39289473985
  Source: `b2b2ad290aae0967559e0cf14002672d32c05584`.
- Exact-byte downloads of 246 wheels (5,373,559,590 bytes) and eight selected
  task inputs (222,386,501 bytes) passed on Actions. The eight model inputs have
  resolved scoped URLs and headers; the 23.3GB model body has not been downloaded
  or executed in this migration.
  Run: https://github.com/hynk-studio/backtrace/actions/runs/39275511563
- At 2026-10-19T15:49:08Z the account API reported balance USD 9.8508333333,
  zero current spend and Auto-Pay disabled. Complete Pod listing contained no
  resources. All four regional exact hardware quotes returned no available machine; this is
  a point-in-time observation, not a reservation or forecast.
- No new GPU allocation, model server start or public task execution.
- Actual transport rebuild matched both prior hashes. Mutual TLS, strict SSH,
  wrong-host rejection, clean child environment and a 147,456-byte private
  transfer passed on the real free runner. The fixed Actions profile also passed.
- All 11 original references (491,594 bytes) passed frozen hash verification
  after ephemeral age transfer. The exact offline runtime installed and imported
  successfully: 245 application distributions with installation network blocked.
  Run: https://github.com/hynk-studio/backtrace/actions/runs/39280774887
- That run stopped during the 214,241,984-byte selected snapshot download after
  three interrupted transfers, with 97,865,169 bytes received. The next change
  bounds large saved-output HTTP requests to 16MiB, validates every Content-Range
  and retains the original full-file hash. Overall deadlines remain unchanged;
  no-progress retries remain bounded. The bounded-range run then verified all eight
  task bodies (222,386,501 bytes) at 2026-10-19T16:13:50Z.
  Run: https://github.com/hynk-studio/backtrace/actions/runs/39282188153
- The next CPU construction check found no logical selected-input mount on the
  plain Actions VM. Free preparation now copies the already verified task bytes
  to the same read-only `/kaggle/input/r0-inputs` path used by Pod activation.
  The retained discovery check and scientific driver remain unchanged; actual
  wrapper construction passed on the real free runner, with no model start.
  All stages passed in run https://github.com/hynk-studio/backtrace/actions/runs/39284346940
  at source `fb74d7ffcaec1f25b04ff655063b55c910894212`. The actual selected-task
  download took 588.285 seconds inside its unchanged 600-second free-test limit.
  The wrapper was adk-submission 0.2.11 with TP1/native BF16 and injected A100 SM80;
  no model/server/task execution occurred. The report SHA256 and 38 source/input
  fingerprints are retained in `a100-actions-qualification.json`.

## Implemented components

`direct_delivery.py` downloads exact files directly on the receiving host using
short-lived HTTPS storage URLs. A separate owner-side resolver must obtain those
URLs. The downloader sends no account authorization header, refuses redirects and
unreviewed hosts, validates strict Range responses after an interrupted body, has
bounded retries and a shared deadline, and verifies every original size/hash.
Single-member ZIP transport is decoded only to the expected file. Wrong bytes,
extra files, bad paths and expired deadlines never activate the input directory.

`cloud_state.py` writes only allowlisted metadata to the dedicated
`bt-001-a100-state` branch. Its fixed authorization claim is create-only, read
back before a provider POST can be attempted, and never reset on a timeout,
restart or empty provider list. Local bootstrap keys, signed URLs and payloads
are excluded from this public record. Prior wallet consumption is included in
the two-hour quote. Ordinary workflow reruns cannot claim another allocation.

`cloud_watch.py` runs in a separate Actions workflow. It observes the exact
controller run and its heartbeat, finds a lost create response by the immutable
random Pod name, and only stops/deletes that owned Pod. Two exact-ID/list absence
reads establish deletion. No resource observed after an uncertain create is
reported separately from confirmed deletion. GitHub write failure cannot suppress
provider cleanup after the claim has been read. The watcher contains no create
operation and does not start the workload.

The cleanup workflow is now scoped to the exact
`bt-001-a100-watch-20261020b` branch; it is not triggered by routine PR pushes.
Its independent concurrency group never cancels a running watcher. The
`claim_before_create` integration seam also checks that this separate workflow
is currently running at the same source SHA before allowing a claim. The state
branch preserves all previous consumed claims. The new watcher branch has been
activated, while its dedicated paid start branch is absent and its claim unused.
The owner workflow runs free preflight on the
qualification branch; paid mode exists only on the dedicated start branch and
requires the successful recorded qualification, unchanged fingerprints and a
full CPU pass at its exact source. It also rechecks the live watcher before
consuming the create-only claim.

## Resolved checks after observed service delays

At 2026-10-19T16:46Z, GitHub's official status API described delayed Actions
workflow status updates, Pages deployments and webhooks:
https://www.githubstatus.com/incidents/8tzbpcnl75jp
The earlier 233-test log and uploaded artifact had passed while its
workflow API still reported in-progress. The required terminal-success gate
remains active. Owner preflight run 39287452412 observed successful qualification
at 16:46:01Z and rebuilt/validated transport, then failed at 16:50:24Z while
resolving the pinned r0-clean.zip source after bounded read-timeout retries.
No paid claim, watcher/start activation or provider allocation occurred.
Free preflight reruns are permitted on the qualification branch; paid mode
still requires run attempt 1 on its exact start branch, plus the create-only claim.

At 16:48:30Z, the separate read-only check again authenticated to RunPod and
listed zero Pods. Model v2 and private notebook v3 checks passed; the small
selected-task probe hit a read timeout. The full selected-task body verification
above remains a distinct successful observation. Regional stock querying is now
an independent workflow step so an unrelated input-probe timeout cannot hide
current account or inventory results. No automatic paid retry is enabled.
At 16:50:59Z, balance remained USD 9.8508333333, spend rate zero and Auto-Pay
disabled. The broad catalog showed CA-MTL-3 LOW, but exact qualified quotes
returned no allocatable offer. This discrepancy is preserved rather than
treating broad availability as an allocation guarantee.

The follow-up owner preflight passed at 16:57:40Z after observing both successful
qualification workflows. It resolved all 246/8/8 wheel/task/model sources and
finished all free checks. The earlier timeout and provider status delay were
not ignored or replaced by synthetic success.

## Remaining launch prerequisites

The frozen driver remains
`9542d7c47eb394247fb30a61a90303ba381b3f0eadbf6a6ef8fb8939bae7f342`.
Input downloads, original-reference verification, transport build/loopback,
offline runtime, actual wrapper construction and owner preflight have passed.
Model execution and the public task have not started.

1. Refresh a matching region/hardware quote, wallet and Auto-Pay through the
   account API. Run the independent watcher and one owner workflow only after
   every free gate is satisfied. Never reset a claim or retry a paid create.
2. Retain encrypted private results, obtain two independent owned-resource
   absence checks, and refresh actual account spending after completion.

The free preparation receiver generates an ephemeral age identity on its runner.
Only its public recipient and encrypted original reference archive appear in the
separate `a100-transfer/` namespace. Every original reference file must match
`source-manifest.json`; newer competition downloads are not substituted. The
receiver has no RunPod secret or allocation path. Immutable input reads have at
most three retries for transient transport/server errors; hashes and identity
errors never retry or change a pin.

Private evidence uses standard age encryption to the owner's separately retained
recipient. A real uploaded artifact was downloaded, decrypted and matched to the
pinned original notebook. Neither account keys, SSH private keys nor scoped URL
maps are included in the public report or encrypted evidence allowlist.

Free preparation is qualified at the recorded source. The paid entry still
requires a fresh qualified offer, the live independent watcher and the unused
create-only claim; a successful preflight does not reserve stock. An Actions/GitHub or
provider outage can still delay cleanup; no provider hard timer is claimed.

References #1. No merge, Issue #1 closure, training or submission.

### Latest resumption — 2026-10-20 21:11 KST

The owner explicitly directed resumption. Complete renewed free qualification
passed at source `d6c48e49950aa1120d7d4828ed8a9ce8fc28a0d8`, run 39421393404.
After one zero-create stock miss, the fresh authorization allocated a single
CA-MTL-3 Pod and is now consumed and independently deleted. All 28.9GB of
frozen input bodies verified, but installation was interrupted by an unspecified
controller StateError before any model/task execution. The exact condition is
unconfirmed; free timestamp-observation and error-retention improvements are
kept separate from that diagnosis. The one-shot automatic resumption was
disabled. Read [the latest execution record](a100-execution-20261020-2111.md).
