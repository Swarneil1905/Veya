"""Approved synthetic ERP execution, with authoritative final-state verification."""

import json
from dataclasses import replace

from veya.domain.models import DomainError, Run
from veya.events.store import append_event
from veya.finance.agent import InvoicePacket, assess
from veya.storage.run_state import persist_transition
from veya.storage.sqlite import decode
from veya.tools.execution import ToolExecutor
from veya.tools.retries import ToolFailure


async def execute(agent, executor, actor, erp, run_id, approval_id):
    if (
        actor.tenant_id != agent.tenant
        or erp.tenant != agent.tenant
        or executor.intents.db.path != agent.db.path
        or erp.db.path != agent.db.path
    ):
        raise DomainError('forbidden', 'Finance execution scope differs')
    try:
        return await _execute(agent, executor, actor, erp, run_id, approval_id)
    except DomainError as error:
        row = agent.get(run_id)
        assessment = json.loads(row['assessment_json'])
        result = dict(
            state='unresolved',
            reason='authorization_denied' if error.code == 'forbidden' else 'state_mismatch',
            draft_id=None,
            run_id=run_id,
            proposal_id=row['proposal_id'],
            approval_id=approval_id,
            evidence=assessment['evidence'],
            fixture=True,
        )
        with agent.db.transaction() as conn:
            # A rejected retry must not erase an already verified success.
            latest = conn.execute(
                'SELECT outcome_json FROM finance_resolutions WHERE tenant_id=? AND run_id=?',
                (agent.tenant, run_id),
            ).fetchone()[0]
            if not latest or json.loads(latest)['state'] != 'succeeded':
                conn.execute(
                    'UPDATE finance_resolutions SET outcome_json=? WHERE tenant_id=? AND run_id=?',
                    (json.dumps(result), agent.tenant, run_id),
                )
            append_event(conn, agent.tenant, run_id, 'finance.unresolved', result)
        raise


async def _execute(agent, executor, actor, erp, run_id, approval_id):
    row = agent.get(run_id)
    packet = InvoicePacket.model_validate_json(row['packet_json'])
    expected = json.loads(row['assessment_json'])
    if assess(agent.db, agent.tenant, packet) != expected or not row['proposal_id']:
        raise DomainError('conflict', 'Evidence changed or resolution needs clarification')
    proposal = agent.proposals.get(agent.tenant, row['proposal_id'])
    original = executor.bindings[(proposal.tool_name, proposal.tool_version)]

    def current_resources(arguments):
        if assess(agent.db, agent.tenant, packet) != expected:
            raise DomainError('conflict', 'Source evidence changed before dispatch')
        return original.resources(arguments)

    executor = ToolExecutor(
        executor.intents,
        executor.workspace_id,
        executor.policy,
        (replace(original, resources=current_resources),),
        approvals=executor.approvals,
        budgets=executor.budgets,
    )
    # Validate authority before changing the run state. The executor rechecks it
    # again immediately before the external effect.
    review = executor.review(actor, agent.scope, run_id, proposal.id)
    if executor.approvals is None or approval_id is None:
        from veya.policy.engine import PolicyDenied

        raise PolicyDenied('missing_approval')
    executor.approvals.verify(executor.approvals.get(agent.tenant, approval_id), review)
    with agent.db.transaction() as conn:
        current = decode(
            Run,
            conn.execute(
                'SELECT payload FROM runs WHERE tenant_id=? AND id=?', (agent.tenant, run_id)
            ).fetchone()[0],
        )
        if current.state in {'waiting', 'queued'}:
            persist_transition(conn, current, 'running', current.revision)
        elif current.state not in {'running', 'succeeded'}:
            raise DomainError('conflict', 'Stopped run cannot execute a resolution')
    reason = None
    try:
        outcome = await executor.execute(
            actor, agent.scope, run_id, proposal.id, approval_id=approval_id
        )
        if outcome.state not in {'succeeded', 'unresolved'}:
            reason = 'execution_incomplete'
    except ToolFailure:
        reason = 'external_outcome_unknown'
    # Reconcile after timeout. Never infer a successful draft from local completion.
    result: dict
    final = erp.reconcile(proposal.arguments)
    if final is None:
        result = {'state': 'unresolved', 'reason': reason or 'state_mismatch', 'draft_id': None}
    else:
        actual = erp.read(run_id)
        if (
            actual['invoice'] != packet.invoice.model_dump(mode='json')
            or actual['resolution'] != expected['resolution']
        ):
            raise DomainError('conflict', 'ERP state differs from the approved proposal')
        result = {'state': 'succeeded', 'reason': None, 'draft_id': final['draft_id']}
    result.update(
        run_id=run_id,
        proposal_id=proposal.id,
        approval_id=approval_id,
        evidence=expected['evidence'],
        fixture=True,
    )
    with agent.db.transaction() as conn:
        conn.execute(
            'UPDATE finance_resolutions SET outcome_json=? WHERE tenant_id=? AND run_id=?',
            (json.dumps(result), agent.tenant, run_id),
        )
        append_event(conn, agent.tenant, run_id, 'finance.verified', result)
        current = decode(
            Run,
            conn.execute(
                'SELECT payload FROM runs WHERE tenant_id=? AND id=?', (agent.tenant, run_id)
            ).fetchone()[0],
        )
        if result['state'] == 'succeeded' and current.state == 'running':
            persist_transition(conn, current, 'succeeded', current.revision)
        elif result['state'] == 'unresolved' and current.state == 'running':
            persist_transition(conn, current, 'waiting', current.revision)
    return result
