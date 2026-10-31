# E2B twenty-case attempt: common-runtime transfer timed out

Run [41219228584](https://github.com/hynk-studio/backtrace/actions/runs/41219228584)
at `dc5ab2b96f5b51da67ff9c74c0acd2f063fc7322` allocated one NVIDIA L40S
in EUR-IS-2, Pod `y7l7yv30jmumx2`. Its 1,640-second allocation-inclusive
contract and 1,220-second work limit remained unchanged. The source had passed
698 native tests, all 17 container controls, and exact checkpoint/input checks
in free qualification 41218223100.

The authenticated 1,400,320-byte SSH executable arrived. The subsequent common
runtime transfer failed at `private_delivery.push -> receiver.wait` with
`TimeoutExpired`, under its unchanged 600-second ceiling. This is the same
3,642,457,480-byte runtime phase that failed in E4B run 41210831659, now on a
different GPU/region. It preceded installation, actual CUDA checks, checkpoint
transfer, all 20 untrained Augnes decisions, and all four training updates.
All **21 assigned generations remain NOT_RUN**. No model output or adapter was
produced. The outer `RuntimeError: hardware diagnostic failed` is a wrapper,
not evidence of an observed CUDA or model failure.

Both independent controllers confirmed deletion with two complete absence reads
at least 90 seconds apart. The watcher completed at16:42:52.944 UTC and the
owner at16:43:30.220 UTC. The owner sent DELETE at16:40:28.754 UTC. At16:43:31
credit was USD2.1973672941, spend was zero and autopay was off; the complete
16:43:40 inventory contained zero Pods. The observed balance decrease was
USD0.2132034732 for this attempt and USD0.7086768398 for this continuation,
subject to provider final billing. USD0.2913231602 remains under the current
USD1 continuation ceiling. No additional allocation is started by this record.

[Raw evidence](evidence/screen-probe-run-41219228584/provenance.json) preserves
all nine members of both archives, both cleanup state blobs, the early failure
state, and a 21-row NOT_RUN manifest. Both ZIP digests, all member bytes,
180 nested source-hash entries across82 unique paths, state Git blob hashes,
claim/Pod bindings and independent controller identities were verified.

The two timeouts do not establish whether network throughput, sender work,
receiver I/O or another transport condition dominated. Existing diagnostics
discarded SSH streams and retained no byte-progress observations. The receiver
already used `-W1048576`; it was not using Dropbear's 24KiB default. A larger
receive window is a specific hypothesis for a latency-sensitive throughput
limit, not a proven historical cause. A free, same-payload/same-delay comparison
must test that hypothesis before a changed paid route. Preserve the failed
source/start/permit and all denominators. Do not repeat this unchanged transfer,
extend its running limits, weaken authentication, or count preparation as model
evidence. The practical-model objective remains incomplete.
