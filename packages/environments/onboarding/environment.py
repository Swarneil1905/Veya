"""Reproducible employee fixture. No real identity provider is contacted."""

from veya.onboarding.agent import AccessWorkflow


def create(db, tenant='fixture_onboarding'):
    workflow = AccessWorkflow(db, tenant, {'analyst': frozenset({'reports_read'})})
    workflow.add_subject('new_hire', 'manager', 'analyst')
    return workflow
