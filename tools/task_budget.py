"""Review task budgets against nested process and provider deadlines.

This module never edits the frozen candidate, launches a model, or authorizes
compute. A proposal is a different experimental budget, not a repaired score.
"""
import math

PROPOSAL = {
    'protocol': 'R0-budget-calibration-v1', 'status': 'REVIEW_ONLY_NOT_ACTIVATED',
    'session_seconds': 300, 'tool_calls': 30, 'llm_calls': 50,
    'command_seconds': 60, 'agent_child_seconds': 330,
    'agent_teardown_seconds': 30, 'server_startup_seconds': 1200,
    'retrieval_seconds': 180, 'provider_cleanup_seconds': 300,
}


def check(profile, useful_remaining, total_remaining):
    fields = set(PROPOSAL) - {'protocol', 'status'}
    if (set(profile) != set(PROPOSAL)
            or any(type(profile[k]) is not int or profile[k] <= 0 for k in fields)
            or any(type(x) not in (int, float) or not math.isfinite(x) or x < 0
                   for x in (useful_remaining, total_remaining))):
        raise ValueError('finite positive task budget and remaining deadlines required')
    reasons = []
    child = profile['session_seconds'] + profile['agent_teardown_seconds']
    if profile['agent_child_seconds'] < child:
        reasons.append('agent child expires before the inner session and teardown')
    useful = (profile['server_startup_seconds'] + profile['agent_child_seconds']
              + profile['retrieval_seconds'])
    total = useful + profile['provider_cleanup_seconds']
    if useful_remaining < useful:
        reasons.append('insufficient useful time for startup, task and retrieval')
    if total_remaining < total:
        reasons.append('insufficient total time including confirmed provider cleanup')
    return {'status': 'BLOCKED' if reasons else 'PASS', 'reasons': reasons,
            'minimum_useful_seconds': useful, 'minimum_total_seconds': total,
            'compute_authorization': 'NONE',
            'predicts_task_success': False}
