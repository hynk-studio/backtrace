# Actions controller migration

The owner accepted the cloud-browser/Actions/RunPod proposal at 20:31:26 KST
on 2026-10-19. The new policy is `a100-cloud-policy.json`: setup up to 90 minutes,
allocation through confirmed deletion up to two hours, one further allocation,
server start and public task at most, within the existing USD 10 wallet and
USD 8 cumulative stop. The prior CA-MTL-3 attempt remains consumed and deleted.

## Observed execution

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
- Latest actual CPU test output: **233/233**, 29.473 seconds, preflight READY.
  Run: https://github.com/hynk-studio/backtrace/actions/runs/39287452398
  Source: `6cd9fbf181e271b96cfb5b68dcc9167bbbfa2020`.
  The log finished at 16:41:41Z, but the API still reported in-progress afterward;
  this is not recorded as a successful workflow conclusion.
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

The cleanup workflow is scoped to the exact
`bt-001-a100-watch-20261019` branch; it is not triggered by routine PR pushes.
Its independent concurrency group never cancels a running watcher. The
`claim_before_create` integration seam also checks that this separate workflow
is currently running at the same source SHA before allowing a claim. The state
branch is prepared; no claim has been made. The watcher/start trigger branches
have not been activated. The owner workflow runs free preflight on the
qualification branch; paid mode exists only on the dedicated start branch and
requires the successful recorded qualification, unchanged fingerprints and a
full CPU pass at its exact source. It also rechecks the live watcher before
consuming the create-only claim.

## Observed provider status delay

At 2026-10-19T16:46Z, GitHub's official status API described delayed Actions
workflow status updates, Pages deployments and webhooks:
https://www.githubstatus.com/incidents/8tzbpcnl75jp
The current test log and uploaded artifact show 233 passing tests, while its
workflow API still reports in-progress. The required terminal-success gate
remains active. Owner preflight run 39287452412 is still pending; no paid claim,
watcher/start activation or provider allocation has occurred.

At 16:48:30Z, the separate read-only check again authenticated to RunPod and
listed zero Pods. Model v2 and private notebook v3 checks passed; the small
selected-task probe hit a read timeout. The full selected-task body verification
above remains a distinct successful observation. Regional stock querying is now
an independent workflow step so an unrelated input-probe timeout cannot hide
current account or inventory results. No automatic paid retry is enabled.

## Remaining launch prerequisites

1. Complete the new owner workflow's actual free preflight and full CPU suite.
   Input downloads, original-reference verification, transport build/loopback,
   offline runtime and actual cloud-policy wrapper construction have passed.
   The frozen driver remains
   `9542d7c47eb394247fb30a61a90303ba381b3f0eadbf6a6ef8fb8939bae7f342`.
2. Refresh a matching region/hardware quote, wallet and Auto-Pay through the
   account API. Run the independent watcher and one owner workflow only after
   every free gate is satisfied. Never reset a claim or retry a paid create.
3. Retain encrypted private results, obtain two independent owned-resource
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

Until those prerequisites pass, the new code is migration preparation and
**not authorization to invoke an unqualified paid entry**. An Actions/GitHub or
provider outage can still delay cleanup; no provider hard timer is claimed.

References #1. No merge, Issue #1 closure, training or submission.
