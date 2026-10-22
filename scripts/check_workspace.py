"""Fail early with a named prerequisite before installing workspace dependencies."""
from pathlib import Path
import argparse


def check(root: Path) -> None:
    for relative, label in [
        ('apps/desktop/package.json', 'desktop package'),
        ('services/runtime/pyproject.toml', 'Python sidecar package'),
        ('services/runtime/veya/__init__.py', 'Python sidecar module'),
        ('pnpm-workspace.yaml', 'pnpm workspace'),
    ]:
        if not (root / relative).is_file():
            raise ValueError(f'Missing prerequisite: {label} ({relative})')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    try:
        check(args.root)
    except ValueError as error:
        parser.exit(1, str(error) + '\n')
    print('Workspace prerequisites present.')
