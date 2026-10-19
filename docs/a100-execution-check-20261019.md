# A100 execution check — 2026-10-19

**Blocked before create: the fixed EU-RO-1 region is out of stock.**
The owner confirmed the existing USD 10 funding and directed execution after
the small-request transport qualification. That instruction was acted on by
recovering the free CPU controller and reconciling live RunPod state. No new
create request was sent, so this instruction has not been consumed by a create.

## Observed state

- Qualified source: `6c83710cea4248f0e9a2e3ea3148320ec5f9aecf`.
  Recovery verified all 41 tool/test hashes, prepared manifests and private
  transport identities. The existing 162-test CPU qualification remains the
  evidence for unchanged tooling; no new full-suite claim is made.
- Two complete authenticated Pod lists, at `2026-10-19T08:45:27.519634Z` and
  `2026-10-19T08:45:28.431142Z`, returned **zero Pods**.
- Authenticated REST v2 catalog: A100 PCIe 80GB / Secure / count 1 / minimum
  CUDA 12.8 returned availability `LOW`, with **US-MO-1 as its sole returned
  data center**. CUDA 13.0 was available; 12.8 and 13.2 were unavailable.
  The exact EU-RO-1 console filter independently showed **Out of capacity**
  and **Instance not available**.
- Billing API returned **zero records / USD 0 total** for its reported
  2026-09-26 through 2026-10-20 UTC query window. The refreshed account UI
  showed **USD 10.00 balance**, **USD 0.000/hour** spend and **Auto-Pay disabled**.
  The UI states billing data is one hour behind; this is observed billing,
  not a stronger guarantee about unreported usage.
- The first failed-create journal is byte-identical, SHA256
  `c12636234c1b57c60fdc320ba7f28b736398f9a81486ab302339ce9e21bf06fd`.
  Its historical `cleanup_unresolved` / null Pod ID is preserved, not relabeled
  as a deleted allocation. No history archival, rearming or state-path change
  was performed because no qualified offer exists in the approved region.

This follow-up made **zero create requests, allocations, inference starts and
task executions**. No new charge, funding, automatic deployment subscription,
training, competition submission or merge was initiated. The free CPU session
was stopped after its private status checkpoint was saved.

## Concrete region-only proposal

The console's exact US-MO-1 selection offered:

| Property | Observed / proposed |
| --- | --- |
| GPU | One A100 PCIe, 80GB VRAM, Secure |
| Host | 125GB RAM, 12 vCPU; available CUDA 13.0 |
| Compute | USD 1.79/hour |
| Storage | 100GB temporary container disk, USD 0.014/hour; no persistent volume |
| Combined observed rate | USD 1.804/hour; rounded UI total USD 1.80/hour |
| 50-minute usage estimate | About USD 1.5034 at that rate, before any unreported adjustment |
| Proposed change | EU-RO-1 → US-MO-1 only |

The pinned image, transport, checkpoint, task, one-allocation / one-server /
at-most-one-task limits, setup deadline, 3,000-second total window, USD 10
existing wallet, USD 8 cumulative early stop and independent cleanup would
remain unchanged. Stock is not reserved. Internet transfer time is unmeasured
in either region and remains inside the existing deadline.

The existing plan and controller explicitly fix EU-RO-1. The alternative above
is therefore a reviewable proposal requiring the owner's region amendment;
no code, private plan or paid execution has been switched to the US. After
that amendment, update and qualify the region checks, refresh the offer,
preserve and reconcile the original journal, and perform only the newly
directed single create. No automatic retry is enabled.

Raw read-only evidence and checkpoint are retained privately in the owner's
Kaggle notebook. No credential, model, task data or private transport identity
is published. Draft PR #7 and Issue #1 remain open.
