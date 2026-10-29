"""Explicit local operator commands. No remote publication or implicit authority.

Finance commands operate only on fixture_* tenants and a synthetic ERP. The
approve command is an explicit review action, separate from execute. Key files
are supplied by the host administrator; their contents are never printed.
"""

# ruff: noqa: E402
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'services/runtime')]
from veya.domain.models import DomainError
from veya.storage.sqlite import Database


def read(path, limit=1048576):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Invalid bounded host input')
    return path.read_bytes()


def key(path):
    value = read(path, 32)
    if len(value) != 32:
        raise ValueError('Key file must contain exactly 32 raw bytes')
    return value


def finance(db, tenant):
    from veya.finance.agent import FinanceAgent
    from veya.tools.proposals import ProposalStore
    from veya.tools.registry import ToolRegistry, ToolScope

    from packages.connectors.fixture_erp.adapter import definition

    if not tenant.startswith('fixture_'):
        raise ValueError('Finance host currently supports synthetic ERP tenants only')
    registry = ToolRegistry()
    registry.register(definition())
    return FinanceAgent(
        db,
        tenant,
        ProposalStore(db, registry),
        ToolScope(tenant, frozenset({'fixture_erp_draft'}), frozenset({'fixture_erp_write'})),
    )


def authority(agent, run_id, actor_id, signing_key):
    from dataclasses import replace

    from veya.policy.approvals import ApprovalStore
    from veya.policy.engine import Actor, Grant, PolicyEngine
    from veya.tools.execution import ToolExecutor
    from veya.tools.idempotency import IntentStore

    from packages.connectors.fixture_erp.adapter import FixtureERP
    from packages.connectors.rate_limits import ConnectionLimiter

    row = agent.get(run_id)
    proposal = agent.proposals.get(agent.tenant, row['proposal_id'])
    erp = FixtureERP(agent.db, agent.tenant, 'finance_fixture')
    actor = Actor(actor_id, agent.tenant, 'finance_fixture')
    grant = Grant(
        'fixture_review',
        actor,
        'fixture_erp_draft',
        'write',
        'fixture_erp_write',
        erp.resource(proposal.arguments)[0],
        proposal.id,
    )
    approvals = ApprovalStore(agent.db, signing_key, 'operator_key')
    limiter = ConnectionLimiter(agent.db, agent.tenant)
    limiter.configure('fixture_erp', capacity=60, interval=60, parallelism=4)
    binding = erp.binding()

    async def bounded(arguments):
        return await limiter.call('fixture_erp', run_id, lambda: binding.handler(arguments))

    executor = ToolExecutor(
        IntentStore(agent.proposals),
        'finance_fixture',
        lambda: PolicyEngine('fixture_policy', frozenset({'fixture_erp_write'}), (grant,)),
        (replace(binding, handler=bounded),),
        approvals=approvals,
    )
    return executor, actor, erp


async def dispatch(args):
    from veya.storage.recovery import inspect, restore_preserving_original

    if args.command == 'inspect':
        return inspect(args.workspace)
    if args.command == 'restore':
        return {
            'restored': str(
                restore_preserving_original(args.workspace, args.snapshot, args.destination)
            ),
            'read_only': True,
        }
    db = Database(args.workspace)
    if args.command == 'webhook':
        from veya.connections.webhooks import Webhooks

        return Webhooks(db, args.tenant, args.connection, key(args.key_file)).ingest(
            read(args.body, 65536), args.timestamp, args.signature
        )
    if args.command == 'alert-sample':
        from veya.observability.alerts import Alerts

        return Alerts(db, args.tenant).sample(
            args.source, args.failures, args.attempts, timestamp=args.timestamp
        )
    if args.command == 'protected-export':
        from veya.privacy.export import export_protected

        scope = json.loads(read(args.scope))
        # Authority is the exact host-selected scope file, never model/renderer input.
        expected = {'tenant': args.tenant, 'run': args.run, 'artifacts': args.artifact}
        return export_protected(
            db,
            args.tenant,
            args.run,
            tuple(args.artifact),
            args.destination,
            key=key(args.key_file),
            key_id=args.key_id,
            policy_version='host_export_v1',
            authorize=lambda t, r, a: (
                json.loads(read(args.scope)) == scope == expected
                and (t, r, a) == (args.tenant, args.run, tuple(args.artifact))
            ),
        )
    agent = finance(db, args.tenant)
    if args.command == 'prepare':
        from veya.finance.agent import InvoicePacket
        from veya.finance.batch import InvoiceBatch

        packets = tuple(
            InvoicePacket.model_validate_json(json.dumps(value))
            for value in json.loads(read(args.packets))
        )
        return await InvoiceBatch(agent).prepare(args.id, packets)
    if args.command in {'batch-status', 'cancel-batch'}:
        from veya.finance.batch import InvoiceBatch

        batch = InvoiceBatch(agent)
        return batch.cancel(args.id) if args.command == 'cancel-batch' else batch.status(args.id)
    if args.command == 'report':
        from veya.finance.report import result_pack

        return result_pack(agent, args.run)
    executor, actor, erp = authority(agent, args.run, args.actor, key(args.key_file))
    if args.command == 'approve':
        from dataclasses import asdict

        review = executor.review(actor, agent.scope, args.run, agent.get(args.run)['proposal_id'])
        return asdict(executor.approvals.issue(review, expires_at=time.time() + 600))
    if args.command == 'revoke':
        executor.approvals.revoke(args.tenant, args.approval, args.actor)
        return {'revoked': args.approval}
    from veya.finance.execute import execute

    return await execute(agent, executor, actor, erp, args.run, args.approval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--tenant', required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('inspect')
    p = commands.add_parser('restore')
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--destination', type=Path, required=True)
    p = commands.add_parser('prepare')
    p.add_argument('--packets', type=Path, required=True)
    p.add_argument('--id', required=True)
    for command in ('batch-status', 'cancel-batch'):
        commands.add_parser(command).add_argument('--id', required=True)
    commands.add_parser('report').add_argument('--run', nargs='+', required=True)
    for command in ('approve', 'execute', 'revoke'):
        p = commands.add_parser(command)
        p.add_argument('--run', required=True)
        p.add_argument('--actor', required=True)
        p.add_argument('--key-file', type=Path, required=True)
        if command != 'approve':
            p.add_argument('--approval', required=True)
    p = commands.add_parser('webhook')
    for field in ('connection', 'timestamp', 'signature'):
        p.add_argument('--' + field, required=True)
    for field in ('body', 'key-file'):
        p.add_argument('--' + field, type=Path, required=True)
    p = commands.add_parser('alert-sample')
    p.add_argument(
        '--source', choices=['runtime', 'provider', 'connector', 'finance'], required=True
    )
    p.add_argument('--timestamp', type=float, required=True)
    p.add_argument('--failures', type=int)
    p.add_argument('--attempts', type=int)
    p = commands.add_parser('protected-export')
    for field in ('run', 'key-id'):
        p.add_argument('--' + field, required=True)
    p.add_argument('--artifact', action='append', default=[])
    for field in ('scope', 'destination', 'key-file'):
        p.add_argument('--' + field, type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(asyncio.run(dispatch(args)), indent=2))
    except (DomainError, ValueError, OSError):
        print(
            json.dumps(
                {
                    'error': 'operation_rejected',
                    'details': 'Check scope, source state and host inputs.',
                }
            )
        )
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
