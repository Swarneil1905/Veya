"""Local reviewer composition. No tool grants or execution adapters are invented."""

import secrets

from veya.policy.approvals import ApprovalStore
from veya.policy.engine import Actor, PolicyEngine
from veya.policy.inbox import ApprovalInbox
from veya.storage.sqlite import Database
from veya.tools.execution import ToolExecutor
from veya.tools.idempotency import IntentStore
from veya.tools.proposals import ProposalStore
from veya.tools.registry import ToolRegistry, ToolScope


def local_inbox(root, tenant: str) -> ApprovalInbox:
    db = Database(root)
    actor = Actor('local_reviewer', tenant, 'personal')
    registry = ToolRegistry()
    scope = ToolScope(tenant, frozenset(), frozenset())
    policy = PolicyEngine('local_default_deny_v1', frozenset(), ())
    executor = ToolExecutor(
        IntentStore(ProposalStore(db, registry)),
        actor.workspace_id,
        lambda: policy,
        (),
        approvals=ApprovalStore(db, secrets.token_bytes(32), 'session'),
    )
    # Issued receipts intentionally expire across a private-worker restart.
    # Pending requests require current configured tools/policy before any decision.
    return ApprovalInbox(executor, actor, scope)
