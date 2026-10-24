
## Generic review and verification
- Reproduce the reported behavior with a small check before editing. A failing
  assertion must produce a nonzero exit; printing an error is not a failing test.
  Read stdout, stderr and exit status. A successful tool invocation alone does
  not show that the check passed.
- Keep changes small and preserve unrelated behavior. Read each edit response;
  rejected edits are not applied changes. Inspect the final diff for accidental
  files and avoid leaving exploratory reproduction scripts in the patch.
- Reserve at least 6 charged tools and 90 seconds for editing, verification and
  submission. After each accepted implementation edit, rerun the same relevant
  check and an existing nearby regression when affordable. A later edit makes
  earlier verification stale. Do not weaken a check just to make it pass.
- Before submission, review the patch and the checks actually completed. If a
  check failed, could not run, or was not rerun after the last edit, say so.
