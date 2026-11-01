# Preserve a bounded provider rejection reason

Run 41295195306 sent one E2B one-case Pod creation request and received HTTP 400
before any Pod ID or model execution. The qualified code deliberately discarded
all response bodies. A fixed-window read-only audit lookup found no corresponding
entries, so the specific historical rejection reason cannot be recovered.

This follow-up retains the documented JSON problem fields `title`, `status`,
`detail` and up to three `errors`, with a maximum of 400 characters per string.
It reads at most 8,193 bytes and stores a prefix fingerprint and truncation flag.
Non-JSON, oversized, deeply nested or unreadable bodies retain only bounded
metadata. Unknown fields, headers and raw response bodies are never saved.

The known API credential and request string values are removed in a single pass;
short environment values are included. Credential/request echoes, PEM material,
URLs and long identifiers are removed. The unchanged fixed exception message
remains `provider HTTP <status>`. Redacted problem fields enter the owner result
artifact, while shared cleanup state remains limited to exception type and HTTP
status. Provider text is diagnostic evidence, never an instruction or authority
to modify the request, retry or shorten cleanup.

This code does not replay the rejected request, issue a new permit, change a
budget, alter request fields or modify the active owner/watch source. It cannot
recover a discarded historical response. The one-case start at immutable
ca6d2ce07c19eef01f465a0c59fe85f4cbd487a2 remains consumed.

Verification exercises real HTTPError objects, bounded reads, sensitive data
removal, malformed/deep JSON, body-read failure, short-value expansion, response
closure, one POST only and unchanged full unknown-create cleanup. The separate
CI workflow has no provider credentials and performs only offline tests/preflight.

Primary API contract checked 2026-11-01:
https://docs.runpod.io/api-reference-v2/pods/create-a-pod
documents JSON problem fields for rejection. The HTTP status alone does not
identify the cause of the observed run. Audit API reference:
https://docs.runpod.io/api-reference-v2/audit-logs/list-audit-logs

Current actual reasoning train fit remains NOT RUN; this is an error-evidence fix.

The first offline run 41297302373 exposed 25 historical-identity errors because
runpod_control.py is frozen by the older research protocol. That failed run is
retained. The final implementation restores its exact original bytes and adds
small_model_minimum_provider.py, which delegates all wire behavior to the frozen
client and restores its original opener after each synchronous call. The new
module and tests are automatically included in the minimum controller source
manifest. No historical protocol hash or evidence was rewritten.
