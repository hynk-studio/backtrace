# Direct-delivery completion was rejected before allocation

Run41233521859 executed source`f9fd1b42fb76871a3af79819d2c027c46744d446`.
Its owner finished preparation but rejected the current offer before writing a
claim or issuing any provider create request. At19:26:34 UTC the only quoted
USD0.59/hour40GB-or-larger candidate was A40/EU-SE-1, which this candidate had
excluded. The remaining eligible L40S offers wereUSD1.09/hour and projected above
the fixedUSD0.47 allocation cap. The error wording mentions cumulative budget;
the directly observed failing condition is the available permitted route price.

Provider create requests:0. All three model assignments and four updates remain
NOT_RUN. Account observations before and after reportUSD1.9441643765, autopay off
and zero hourly spend; complete inventories at19:26:43 and19:26:51 contain zero
Pods. No additional GPU charge was observed. The independent watcher has no
claim and will exit its bounded1500-second pre-claim wait; it cannot create a Pod.
The start/permit remain immutable and will not be rerun.

All six owner artifact members,200 nested source bindings and the original
assignment outcomes are retained in`evidence/direct-no-allocation-run-41233521859/`.
The archive is artifact13054103855, SHA256
`e31ab3b58d2422c65340c0f97b8989714623318b9742fc6f279802eafaeac5e7`.
The preceding exact-source free qualification passed728 tests,17 controls and
full public runtime/checkpoint receipt; its55 members/292 bindings are retained.

A prospective route amendment removes only the A40/EU-SE-1 exclusion. Its
historical failure concerned the256MiB all-SSH transfer. The newly qualified
transport sends only about36MiB of owner-created bytes over SSH and retrieves
public bulk assets through fixed HTTPS URLs with exact hashes/readback. Thus a
new bounded attempt tests a materially changed delivery mechanism, not an
unchanged rental retry. Neither the old failure nor the free success proves
current provider throughput. The unrelated A6000/US-TX-1 create exclusion remains.

Keep the existingUSD0.47 allocation,USD1.45 continuation andUSD1.4560441339 credit
floor;2020/1600/300/120 second bounds; identical two inputs/four updates/one
post-update generation; all CUDA/isolation/deletion controls. New start/state are
`bt-001-e2b-public-route-start-20261031` and
`bt-001-e2b-public-route-state-20261031`, namespace`e2b-public-route-paid-20261031`.
Fresh exact-source free qualification and a new single-use permit precede any
allocation. No top-up, automatic retry, overlap, merge or Augnes write.
