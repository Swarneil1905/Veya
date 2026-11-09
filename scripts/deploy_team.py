"""Explicit host deployment command; each effect uses a pinned image and configured cluster."""

import argparse
import json
from pathlib import Path

from scripts.verify_release import verify
from services.deployment.kubernetes import KubernetesTarget
from services.deployment.promotion import Promotions, canary


def run(args):
    configuration = json.loads(args.config.read_text())
    target = KubernetesTarget(**configuration['target'])
    journal = Promotions(args.journal)
    if args.command in {'promote', 'adopt'}:
        decision = verify(
            args.evidence_root,
            json.loads(args.evidence.read_text()),
            commit=args.commit,
            artifact_sha256=args.digest.removeprefix('sha256:'),
        )
        if args.command == 'adopt':
            return journal.adopt(
                args.environment,
                args.digest,
                evidence=decision,
                observe=target.observe,
            )
        return journal.stage(
            args.environment,
            args.digest,
            revision=args.revision,
            evidence=decision,
            deploy=target.deploy,
            observe=target.observe,
        )
    if args.command == 'reconcile':
        return journal.reconcile(
            args.environment,
            revision=args.revision,
            operation_stopped=args.owner_stopped,
            observe=target.observe,
        )
    samples = json.loads(args.samples.read_text())
    action = canary(samples, **configuration['canary_policy'])
    if action != 'rollback':
        return {'action': action, 'deployment': journal.status(args.environment)}
    restored = journal.rollback(
        args.environment,
        revision=args.revision,
        deploy=target.deploy,
        observe=target.observe,
    )
    return {'action': 'rolled_back', 'deployment': restored}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--environment', choices=['test', 'staging'], required=True)
    parser.add_argument('--revision', type=int, required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ['promote', 'adopt']:
        command = commands.add_parser(name)
        command.add_argument('--digest', required=True)
        command.add_argument('--commit', required=True)
        command.add_argument('--evidence-root', type=Path, required=True)
        command.add_argument('--evidence', type=Path, required=True)
    reconcile = commands.add_parser('reconcile')
    reconcile.add_argument('--owner-stopped', action='store_true')
    monitor = commands.add_parser('canary')
    monitor.add_argument('--samples', type=Path, required=True)
    print(json.dumps(run(parser.parse_args()), indent=2))


if __name__ == '__main__':
    main()
