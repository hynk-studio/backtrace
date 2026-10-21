# Scoped quote compatibility — 2026-10-20

The read-only account check at 2026-10-20T04:21:02Z reported CA-MTL-3 available
with Low stock and a filtered single A100 80GB PCIe Secure quote: USD 1.79/hour,
117GB host RAM and 31 vCPU. The optional `supportPublicIp` and
`availableGpuCounts` output fields were null. The old controller rejected this
response as `NO_QUALIFIED_REGION`; this was not evidence of zero stock.

Primary schema inspected on 2026-10-20:
https://graphql-spec.runpod.io/ (version 1.1.0). `GpuLowestPriceInput` accepts
the GPU count, region, Secure cloud, public IP, RAM/CPU/disk and CUDA filters;
the corresponding `LowestPrice` summary fields are nullable. The provider's
availability guidance uses filtered `stockStatus`:
https://docs.runpod.io/sdks/graphql/manage-pods .

A public, unauthenticated read-only GraphQL request to
https://api.runpod.io/graphql completed at 2026-10-20T04:25:39.689209Z.
The exact requested filter was one GPU, CA-MTL-3, Secure, public IP required,
RAM at least 117GB, at least 8 vCPU, 100GB disk and CUDA at least 12.8.
The response returned the price/hardware/Low stock above. Counterqueries in
the same request, changing only RAM to 1,000,000GB or GPU count to eight,
returned null stock, price and hardware. Response: 407 bytes; SHA256
`f6deb36f3c6411395f97a316687df8e4c18feb7048399c32753ad4e5dab57478`.
A separate filtered regional availability read also reported CA-MTL-3 true
and the other three regions false. These observations support using the
exact filtered quote when nullable summaries are absent; they do not reserve
capacity or guarantee that a later create will succeed.

The controller now accepts null summaries only alongside the unchanged exact
filtered stock/price/hardware checks. Explicit public-IP false, empty GPU counts,
or counts excluding one still reject the offer. The create request and actual
allocated-resource checks still enforce the original hardware, region, public-IP,
disk, price and one-attempt conditions. No scientific workload, transport,
time limit, budget or paid retry policy changed. All 38 actual qualification
fingerprints remain identical to the successful retained receipt.

Six focused offer tests passed locally. Full local discovery ran 237 tests;
12 existing process-observation cases errored because this execution host's
procfs PID namespace differs from the Python process. CPU preflight is READY.
The required full suite on the real Linux Actions owner host must pass at the
exact new source before any paid launch; no procfs guard is bypassed.

No allocation or provider setting mutation was performed during these reads.
References #1; no merge or competition submission.
