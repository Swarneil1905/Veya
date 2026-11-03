"""Separate evidence discovery, ranking, permission and generation failures."""


def label(*, expected, candidates, context, citations, answer_correct, permitted):
    expected, candidates, context, citations, permitted = map(
        set, (expected, candidates, context, citations, permitted)
    )
    if not (candidates | context | citations) <= permitted:
        return 'permission_failure'
    if not expected:
        return 'no_gold_evidence'
    if not expected & candidates:
        return 'missed_evidence'
    if not expected & context:
        return 'context_omission'
    if not citations or not citations <= context or not citations & expected:
        return 'unsupported_answer'
    return 'grounded_success' if answer_correct else 'generation_failure'
