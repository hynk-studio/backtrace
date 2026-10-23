"""Generic R1 verification revision, without task answers or extra budget.

Reproduce the historical five-minute candidate before applying this explicit
prompt-only scientific delta. Original tool implementations remain unchanged.
"""
import hashlib
from pathlib import Path

from tools import task_calibration as previous

PROTOCOL = 'R1-budget5m-verification-guidance-v2/A10080-TP1'
BUDGET = dict(previous.BUDGET, protocol=PROTOCOL)
BASE_DRIVER_SHA256 = 'eca5e2ee5065419272e99f8407d09e63798801640f2a8005e5189e7aba9f1b79'
GUIDANCE = b'''

## Search and completion budget
- Graph similarity uses indexed function/class identifiers, not prose embeddings.
  Use a bare identifier. After an empty result, use a narrow read-only repository
  text search with run_command, then read the result before revising a hypothesis.
  Do not repeat empty searches or repeatedly read the same unchanged source.
- Use get_status at the start, after reproduction, after an edit, and when a
  low-budget warning appears. It reports the shared budget; delegation shares it.
  Stop exploration with at least 6 charged tools and 90 seconds left. Reserve
  that capacity for a minimal edit, the same check, one correction if justified,
  a final check/diff, and submit_patch. Do not increase the declared budget.

## Reproduction, correction, and verification
- Establish one small discriminating check before changing implementation. Its
  assertions must fail with a nonzero exit on the original behavior. Never catch
  an assertion or exception just to print a failure and exit successfully. Read
  stdout/stderr as well as exit_code: tool status ok only means the tool ran.
- If a supposed reproduction passes, it has not reproduced the reported failure.
  Check the relevant input and expected behavior instead of guessing a fix.
- State the leading explanation and one plausible alternative; choose a source
  inspection or check that distinguishes them. Avoid changing a shared default
  merely because a value appears in an error. Inspect the relevant caller and
  preserve existing behavior outside the reported case.
- Keep the reproduction and its assertions unchanged while testing a candidate
  correction. Rerun the SAME command after an accepted implementation edit, plus
  a nearby existing regression when affordable. Failure means revise or report
  unresolved; it is not evidence of success. If the reproduction itself was wrong,
  explain why and re-establish its original failure before claiming a correction.
- Read each editing tool response. An error, budget rejection, or missing result
  means the proposed edit was not applied. Inspect the final diff; describe only
  accepted changes and checks actually run. Every later edit invalidates earlier
  verification until the check is rerun. A submitted patch is not a resolved task.
- Call submit_patch within the session. If checks still fail or could not run,
  explicitly report the limitation rather than claiming the issue is fixed.
'''
ANALYZER_GUIDANCE = b'''

## Evidence for the parent
- Return a leading explanation, one plausible alternative, and a small check that
  would distinguish them. Keep source observations separate from assumptions.
- Report only source you actually read. Do not claim an unexecuted edit or test.
  Stop redundant inspection so the parent retains its shared verification budget.
'''


def candidate_files(files):
    result = previous.candidate_files(files)
    result['prompts/system.md'] = previous._replace(
        result['prompts/system.md'], previous.GUIDANCE, GUIDANCE)
    result['prompts/analyzer.md'] += ANALYZER_GUIDANCE
    return result


def apply_candidate(root):
    root = Path(root).absolute()
    paths = list(root.rglob('*'))
    if (root.is_symlink() or any(p.is_symlink() for p in paths)
            or {p.relative_to(root).as_posix() for p in paths if p.is_file()} != set(previous.BASE_FILES)):
        raise ValueError('exact extracted baseline directory required')
    before = {name: (root / name).read_bytes() for name in previous.BASE_FILES}
    after = candidate_files(before)
    for name, data in after.items():
        if data != before[name]:
            (root / name).write_bytes(data)
    return {'protocol': PROTOCOL, 'budget': BUDGET,
            'files': {name: hashlib.sha256(data).hexdigest() for name, data in after.items()}}


def driver_source(source):
    if hashlib.sha256(source.encode()).hexdigest() != BASE_DRIVER_SHA256:
        raise ValueError('verification revision requires the exact historical R1 driver')
    result = previous._replace(source, 'RUN_NAME=' + repr(previous.PROTOCOL), 'RUN_NAME=' + repr(PROTOCOL))
    result = previous._replace(result, 'from tools.task_calibration import apply_candidate',
                               'from tools.task_verification import apply_candidate')
    compile(result, '<verification-private-driver>', 'exec')
    return result
