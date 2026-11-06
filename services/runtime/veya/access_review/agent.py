"""Review fixture grants against host policy before proposing any removal."""

import json


def investigate(workflow, subject):
    current = workflow.subject(subject)
    existing = set(json.loads(current['grants_json']))
    allowed = workflow.policy[current['role']]
    return {
        'subject_id': subject,
        'excess': sorted(existing - allowed),
        'missing': sorted(allowed - existing),
        'plan': workflow.propose(subject) if existing != allowed else None,
        'actions_executed': 0,
    }
