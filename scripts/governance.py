"""Trusted local operator commands for withdrawal, retention and reviewed skills."""

# ruff: noqa: E402
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'services/runtime')]

from veya.privacy.retention import RetentionPolicy
from veya.research.store import ResearchStore
from veya.skills.registry import SkillRegistry
from veya.storage.sqlite import Database

from training.data.withdraw import withdraw


def dispatch(args):
    db = Database(args.workspace)
    if args.command == 'withdraw-source':
        return withdraw(ResearchStore(db, args.tenant), args.source)
    policy = RetentionPolicy(db, args.tenant)
    if args.command == 'retention-policy':
        return {'version': policy.configure(args.days, revision=args.revision)}
    if args.command == 'retention-run':
        return policy.run(args.job)
    registry = SkillRegistry(db, args.tenant)
    if args.command == 'review-skill':
        if args.package.is_symlink() or args.package.stat().st_size > 32768:
            raise ValueError('Package must be a bounded local JSON file')
        package = json.loads(args.package.read_text(encoding='utf-8'))
        return {'digest': registry.review(package, reviewer=args.reviewer)}
    if args.command == 'install-skill':
        return registry.install(
            args.id, args.digest, granted_tools=args.granted_tool, revision=args.revision
        )
    if args.command == 'rollback-skill':
        return registry.rollback(args.id, granted_tools=args.granted_tool, revision=args.revision)
    raise ValueError('Unknown governance command')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--tenant', required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('withdraw-source')
    command.add_argument('--source', required=True)
    command = commands.add_parser('retention-policy')
    command.add_argument('--days', type=int, required=True)
    command.add_argument('--revision', type=int, required=True)
    command = commands.add_parser('retention-run')
    command.add_argument('--job', required=True)
    command = commands.add_parser('review-skill')
    command.add_argument('--package', type=Path, required=True)
    command.add_argument('--reviewer', required=True)
    for name in ['install-skill', 'rollback-skill']:
        command = commands.add_parser(name)
        command.add_argument('--id', required=True)
        command.add_argument('--revision', type=int, required=True)
        command.add_argument('--granted-tool', action='append', default=[])
        if name == 'install-skill':
            command.add_argument('--digest', required=True)
    print(json.dumps(dispatch(parser.parse_args()), indent=2))


if __name__ == '__main__':
    main()
