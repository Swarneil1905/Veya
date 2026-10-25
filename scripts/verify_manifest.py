"""Verify the downloaded build artifact itself before accepting a package job."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


def verify(root:Path,expected_commit:str,*,native:bool=False):
    root=root.resolve()
    manifest=json.loads((root/'artifacts/build-manifest.json').read_text(encoding='utf8'))
    if manifest['commit']!=expected_commit or manifest['native']!=native or manifest['signed'] is not False:
        raise ValueError('Artifact provenance or release boundary differs from the requested build')
    seen=set();installers=0
    for line in (root/'artifacts/SHA256SUMS.txt').read_text(encoding='utf8').splitlines():
        digest,name=line.split('  ',1)
        relative=PurePosixPath(name)
        if (not re.fullmatch('[0-9a-f]{64}',digest) or relative.is_absolute() or '..' in relative.parts or
                '\\' in name or ':' in name or name in seen):
            raise ValueError('Invalid or duplicate manifest entry')
        file=root.joinpath(*relative.parts)
        if not file.resolve().is_relative_to(root) or not file.is_file():
            raise ValueError('Manifest file missing or outside the artifact')
        if hashlib.sha256(file.read_bytes()).hexdigest()!=digest:
            raise ValueError('Artifact checksum mismatch: '+name)
        seen.add(name)
        installers+=name.startswith('apps/desktop/src-tauri/target/release/bundle/nsis/') and name.endswith('.exe')
    if not seen or len(seen)!=manifest['files'] or (native and not installers):
        raise ValueError('Artifact is incomplete')
    return len(seen)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path('.'))
    parser.add_argument('--commit',required=True)
    parser.add_argument('--native',action='store_true')
    args=parser.parse_args()
    print(f'Verified {verify(args.root,args.commit,native=args.native)} artifact checksums and commit identity.')
