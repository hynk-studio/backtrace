# Actual E2B completion and four-update adapter result

[Run41236271328](https://github.com/hynk-studio/backtrace/actions/runs/41236271328)
at `2e0a16e9ea8eea8e1d680d84805be85783088b9b` completed the two original unfinished
untrained responses, four real CUDA training updates and one original post-update
generation. Both independent controllers verified deletion of A40/EU-SE-1 Pod
`08cin7wz323sz2`. This closes the implementation feasibility gap. It does not
establish specialist learning, suitability for the owner's12GB GPU, or Augnes value.

## Execution, evidence and cost

Allocation was requested20:01:35.081 UTC; owner completion without failure was
20:10:38.059. Owner deletion was acknowledged20:10:41.813 and confirmed by two
absence reads ending20:13:43.429; watcher independently observed two absences
ending20:12:31.496. The20:13:45 account read showed USD1.8702846922, autopay off
and zero hourly spend. The complete20:13:53 inventory contained zero Pods.
The initial observed charge is USD0.0738796843 and continuation spending
USD1.0357594417; both remain subject to delayed billing. The allocation's capped
projection was USD0.3394722222, within its USD0.47 allowance. No top-up occurred.

The full runtime3,642,464,920 bytes completed transfer/readback in28.023 seconds;
model/job assets10,279,056,027 bytes in42.599 seconds. Public receipt accounted
for22.369 and39.204 seconds respectively. Owner-generated material remained on
authenticated SSH. These observations on one allocation do not establish a
controlled transport speedup or universal regional reliability. All four actual
A/B/C/D CUDA probes and16 hardware/isolation checks passed.

All72 artifact members and264 nested source entries over92 paths match the
executed tree. Eight immutable state records have verified Git blob identities;
claim, Pod, completion and both cleanup receipts have the same claim digest.
All three response wires match the original input tokens/hashes, finished ledger
records and collected raw text/token IDs. Raw records and labeled derivatives
are in [`evidence/public-route-paid-run-41236271328`](evidence/public-route-paid-run-41236271328).

## What the actual training establishes

The frozen four train-only sequences are unchanged, specification SHA256
`fa410198278709388a62c4f77d7c9215fe399f00e8f4c811f412b0bc84c37b84`:
4,915 sequence tokens and480 supervised tokens. Rank4 FP32 delta matrices on
`model.layers.34.self_attn.q_proj` contain22,528 trainable parameters; the BF16
base remains frozen. Seed17, SGD learning rate0.01 and gradient clipping1.0 are
unchanged. Both delta matrices changed, with finite losses/gradients at every step.

| Measurement | Actual result |
| --- | --- |
| Four updates plus post-update checks/save/reload |1.158415474 seconds|
| Per-row losses |1.998757,1.050697,2.328398,2.490938|
| Per-row gradient norms |0.083946,0.032107,0.092163,0.137764|
| Adapter enabled versus disabled maximum logit difference |0.125|
| Disabled adapter versus base maximum logit difference |0.0|
| Saved/zeroed/reloaded versus trained maximum logit difference |0.0|
| Adapter bytes |90,256|
| Training peak allocated memory |14,706,299,904 bytes|
| Training peak reserved memory |22,858,956,800 bytes|

The independently decoded `adapter.safetensors` has two FP32 tensors with shapes
[4,1536] and[4096,4], exact byte offsets and SHA256
`b24c56cf0698f1cc9e5ccf7bef0cce6115c1f76a2b6b876e150fd74f95850252`.
Reload is into the same live model instance after zeroing the deltas; fresh-process
reload has not run. Losses are from different questions and are not a learning
curve. Before/after first-token argmax remains14937. Peak allocated memory already
exceeds12GB; this BF16 training path is not qualified on a4070SUPER12GB.

The post-update B0 probe generated26 tokens in1.494 seconds. Its strict JSON omits
`active_evidence_ids` and all hypothesis probabilities, and the existing scorer
marks it INVALID. Generation after training works, but this one selected probe
cannot estimate a training benefit.

## Complete twenty-response untrained screening

The two new untrained inputs reproduce the original1278/1316 Unicode messages,
ordering and token hashes exactly. They generated163 and126 tokens in7.430 and
5.215 seconds. Both collector records are OK; that status is not semantic success.

For1278 the model proposes a bounded differential probe but uses the invalid
decision enum DISPOSABLE and treats the disputed policy-drift label as evidence
of a contract regression despite matching source bytes. For1316 DIAGNOSE/UNKNOWN
is appropriate, but the next action SOURCE is underspecified and the hypothesis
mistakenly points to resume/historical lookup routes that the packet says work.
Neither output supplies a substantive disconfirming check.

The explicit multi-run derivative combines the18 unchanged original responses
with these two completion responses. It contains20 outputs:19 strict JSON objects,
14 passing the frozen explicit structural checks. These are not accuracy rates.
The original malformed1274 response, first interrupted1278 attempt, unstarted1316
slot, all21 original assignment outcomes and every failed completion attempt are
retained unchanged. The original run is not relabeled as successfully completed.
The unblinded manual review preserves earlier18 assessments and separately assesses
the two new answers against their frozen criteria. No current-flow/additional-main-
model comparison or general-reasoning/specialist learning comparison has run.

## Continue toward the research objective

The completed E2B outputs show insufficient basic diagnostic reliability, while
actual update/save/reload is now feasible. Therefore the already-qualified E4B
fixed20 comparison was activated only after both E2B deletions and raw-result
review. Its exact source is `99ee2509c2b38a0c3e0729cf66b62baaba3e5533`, free
qualification41234822920, permit463f1351daca7b0ff70b1158a89f660c0d621b00 and
paid run41238159872. It is a separate untrained capacity comparison with the same
20 prompts and a USD0.51 allocation/USD1.80 continuation cap. At20:19 UTC it is
still in pre-allocation preparation; no E4B outcome is claimed here.

Use the measured training time/memory and E4B responses to choose a bounded
matched B2/S candidate experiment; four updates do not satisfy that objective.
Keep existing generators, strong-prompt controls, effective-token/context/update
matching and untouched confirmation families. Do not claim specialty or workflow
value from schema repair or an unmatched control. All three connected Augnes
read-only routes still returned connection failures in the latest retained check;
current runtime configuration and live workflow comparison remain unavailable.
Continue independent feasible research; neither deployment nor an Augnes write
is authorized, and no result justifies merging the historical Draft stack.
