"""Verify pinned third-party guidance without executing its code."""
import hashlib
import json
import re
from pathlib import Path


def verify(root: Path) -> tuple[int, int]:
    root = root.resolve()
    lock = json.loads((root / '.agents/skills-lock.json').read_text(encoding='utf-8'))
    if lock.get('schema_version') != 1 or not lock.get('files'):
        raise ValueError('Missing or unsupported skills manifest')
    seen = set()
    skills = set()
    for item in lock['files']:
        relative = item['path']
        if relative in seen:
            raise ValueError(f'Duplicate manifest entry: {relative}')
        seen.add(relative)
        path = (root / relative).resolve()
        if not path.is_relative_to(root / '.agents'):
            raise ValueError(f'Invalid manifest path: {relative}')
        if not re.fullmatch(r'[0-9a-f]{40}', item['commit']):
            raise ValueError(f'Unpinned source: {relative}')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError(f'Local modification: {relative}')
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if blob != item['upstream_git_blob']:
            raise ValueError(f'Upstream blob mismatch: {relative}')
        if path.name == 'SKILL.md':
            body = data.decode('utf-8')
            if not body.startswith('---\n') or '\n---' not in body[4:]:
                raise ValueError(f'Missing skill frontmatter: {relative}')
            frontmatter = body.split('---', 2)[1]
            if not re.search(r'^name:\s*\S+', frontmatter, re.M):
                raise ValueError(f'Missing skill name: {relative}')
            if not re.search(r'^description:', frontmatter, re.M):
                raise ValueError(f'Missing skill description: {relative}')
            skills.add(path.parent.name)
    actual = {p.parent.name for p in (root / '.agents/skills').glob('*/SKILL.md')}
    if actual != skills:
        raise ValueError('Untracked skill entry point')
    imported_files = {
        p.relative_to(root).as_posix()
        for directory in ['.agents/skills', '.agents/upstream-licenses']
        for p in (root / directory).rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'
    }
    if imported_files != seen:
        raise ValueError(f'Untracked or missing imported files: {sorted(imported_files ^ seen)}')
    return len(skills), len(seen)


if __name__ == '__main__':
    count, files = verify(Path(__file__).resolve().parent.parent)
    print(f'PASS: {count} skill entry points; {files} files match pinned upstream bytes.')
