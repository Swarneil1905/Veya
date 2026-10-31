"""Unsigned local supply-chain evidence tied to source, lockfiles and exact artifact bytes."""

import argparse
import hashlib
import json
import re
import subprocess
import uuid
from pathlib import Path

LOCKS = (
    'pnpm-lock.yaml',
    'services/runtime/uv.lock',
    'apps/desktop/src-tauri/Cargo.lock',
    'services/platform/go.mod',
    'toolchains.json',
)


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            value.update(chunk)
    return value.hexdigest()


def dependencies(root):
    components = []
    for lock, ecosystem in [
        ('services/runtime/uv.lock', 'pypi'),
        ('apps/desktop/src-tauri/Cargo.lock', 'cargo'),
    ]:
        # Extract only package identity/version blocks, not metadata or dependency edges.
        for block in (root / lock).read_text().split('[[package]]')[1:]:
            name, version = (
                re.search(r'^name = "([^"]+)"$', block, re.M),
                re.search(r'^version = "([^"]+)"$', block, re.M),
            )
            if name and version:
                components.append(
                    {
                        'type': 'library',
                        'name': name[1],
                        'version': version[1],
                        'purl': f'pkg:{ecosystem}/{name[1]}@{version[1]}',
                    }
                )
    # pnpm's packages section includes the resolved transitive identities.
    text = (
        (root / 'pnpm-lock.yaml')
        .read_text()
        .split('\npackages:\n', 1)[1]
        .split('\nsnapshots:\n', 1)[0]
    )
    for match in re.finditer(r"^  '?([^\n]+?)'?:\s*$", text, re.M):
        identity = match[1]
        if '@' not in identity:
            continue
        name, version = identity.rsplit('@', 1)
        components.append(
            {
                'type': 'library',
                'name': name,
                'version': version,
                'purl': f'pkg:npm/{name.replace("@", "%40")}@{version}',
            }
        )
    return sorted({c['purl']: c for c in components}.values(), key=lambda c: c['purl'])


def build(root: Path, artifacts: list[Path], commit: str, *, dirty: bool):
    root = root.resolve()
    if not re.fullmatch('[a-f0-9]{40}', commit) or not artifacts:
        raise ValueError('Source commit and at least one real artifact required')
    subjects = []
    for artifact in artifacts:
        path = artifact.resolve(strict=True)
        if artifact.is_symlink() or not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Artifact must be a file inside the build workspace')
        subjects.append(
            {'name': path.relative_to(root).as_posix(), 'digest': {'sha256': digest(path)}}
        )
    if len({s['name'] for s in subjects}) != len(subjects):
        raise ValueError('Duplicate build artifact')
    inputs = [{'uri': name, 'digest': {'sha256': digest(root / name)}} for name in LOCKS]
    manifest = {
        'schema_version': 1,
        'commit': commit,
        'dirty': dirty,
        'signed': False,
        'artifacts': subjects,
        'inputs': inputs,
        'limitations': [
            'Unsigned evidence; verify trusted CI attestations before release',
            'Dependency inventory covers locks, not native system libraries or container base layers',
        ],
    }
    sbom = {
        'bomFormat': 'CycloneDX',
        'specVersion': '1.5',
        'serialNumber': 'urn:uuid:' + str(uuid.uuid4()),
        'version': 1,
        'metadata': {'component': {'type': 'application', 'name': 'Veya', 'version': commit}},
        'components': dependencies(root),
    }
    provenance = {
        '_type': 'https://in-toto.io/Statement/v1',
        'subject': subjects,
        'predicateType': 'https://slsa.dev/provenance/v1',
        'predicate': {
            'buildDefinition': {
                'buildType': 'https://github.com/Swarneil1905/Veya/build/v1',
                'externalParameters': {'commit': commit, 'dirty': dirty},
                'internalParameters': {},
                'resolvedDependencies': inputs,
            },
            'runDetails': {'builder': {'id': 'veya-local-manifest-v1'}},
        },
    }
    return manifest, sbom, provenance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('artifacts', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, default=Path('artifacts/supply-chain'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    dirty = bool(
        subprocess.check_output(
            ['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=root, text=True
        ).strip()
    )
    reports = build(root, args.artifacts, commit, dirty=dirty)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, report in zip(('manifest.json', 'sbom.cdx.json', 'provenance.json'), reports):
        (args.output / name).write_text(json.dumps(report, indent=2) + '\n')
    print(f'Wrote unsigned evidence for {len(args.artifacts)} artifacts; dirty={dirty}')


if __name__ == '__main__':
    main()
