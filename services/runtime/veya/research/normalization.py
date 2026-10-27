"""Preserve provenance; quarantine incomplete or contradictory tool/approval ordering."""

import json

from veya.research.models import Trajectory


def normalize(raw):
    try:
        trace = Trajectory.model_validate_json(json.dumps(raw))
    except (ValueError, TypeError):
        return {'status': 'quarantined', 'reasons': ['invalid_schema'], 'trajectory': None}
    reasons = []
    events = trace.events
    if [e.sequence for e in events] != list(range(1, len(events) + 1)):
        reasons.append('non_contiguous_sequence')
    if (
        events[0].kind != 'start'
        or events[-1].kind != 'finish'
        or sum(e.kind == 'start' for e in events) != 1
        or sum(e.kind == 'finish' for e in events) != 1
    ):
        reasons.append('incomplete_lifecycle')
    if len({(e.run_id, e.attempt, e.model_id) for e in events}) != 1:
        reasons.append('mixed_attempt_identity')
    proposals = {}
    approved = set()
    executed = set()
    for e in events:
        if e.kind == 'proposal':
            if not e.operation or e.effect is None or e.operation in proposals:
                reasons.append('ambiguous_proposal')
            proposals[e.operation] = e.effect
        elif e.kind == 'approval':
            if e.operation not in proposals or not e.approved:
                reasons.append('invalid_approval')
            else:
                approved.add(e.operation)
        elif e.kind == 'tool':
            if e.operation not in proposals or e.effect != proposals.get(e.operation):
                reasons.append('unproposed_tool')
            if e.effect == 'write' and (e.operation not in approved or e.operation in executed):
                reasons.append('unapproved_or_duplicate_write')
            executed.add(e.operation)
    if set(proposals) - executed:
        reasons.append('unfinished_proposal')
    return {
        'status': 'quarantined' if reasons else 'ready',
        'reasons': sorted(set(reasons)),
        'trajectory': None if reasons else trace,
    }
