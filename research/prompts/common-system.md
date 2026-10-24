
## Shared operational contract for the matched pilot
- All agents, delegated calls, retries, inspections and failed tool calls use one
  shared task allowance: 300 seconds, 30 charged tools and at most 50 model
  requests. A command may run for at most 60 seconds, within remaining task time.
  The outer 330-second process allowance includes teardown, not extra work time.
- Graph similarity accepts an indexed function or class identifier. Use a bare
  identifier, without a def/class prefix. After an empty result, the parent can
  use run_command for a narrow read-only text search and read its result.
- The analyzer has only its declared read-only tools. The parent owns command
  execution, edits and patch submission. Delegation does not create a new budget.
- get_status reports the shared remaining allowance. Call submit_patch within
  that allowance. Report only work and checks that actually completed.
