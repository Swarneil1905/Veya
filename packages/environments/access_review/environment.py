"""Synthetic excessive-permission case with a named reviewing manager."""

from veya.onboarding.agent import AccessWorkflow


def create(db, tenant='fixture_access'):
    workflow = AccessWorkflow(db, tenant, {'analyst': frozenset({'reports_read'})})
    workflow.add_subject(
        'employee',
        'manager',
        'analyst',
        existing=frozenset({'reports_read', 'admin_write'}),
    )
    return workflow
