"""Read-only prerequisite check. Run --bootstrap before dependency installation."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PINS=json.loads((ROOT/'toolchains.json').read_text(encoding='utf8'))


def validate_version(tool:str,output:str,*,exact:bool=False):
    match=re.search(r'(?<!\d)(\d+)\.(\d+)\.(\d+)',output)
    if not match: raise ValueError(f'{tool}: could not parse version')
    version=tuple(map(int,match.groups()))
    pin=tuple(map(int,PINS[tool].split('.')))
    supported={'node':(22,22,3)<=version<(23,0,0),'python':(3,10,0)<=version<(3,14,0)}
    if (version!=pin if exact or tool not in supported else not supported[tool]):
        raise ValueError(f'{tool}: unsupported {match[0]}; pinned version is {PINS[tool]}')
    return match[0]


def check_pins(root:Path):
    for tool,file in [('node','.node-version'),('python','.python-version'),('go','.go-version')]:
        if (root/file).read_text().strip()!=PINS[tool]: raise ValueError(f'{tool}: pin drift in {file}')
    for file in ['package.json','apps/desktop/package.json']:
        if json.loads((root/file).read_text())['packageManager']!='pnpm@'+PINS['pnpm']:
            raise ValueError('pnpm: package-manager pin drift')
    manifest=json.loads((root/'package.json').read_text())
    if manifest['dependencies']['@angular/core'] != PINS['angular'] or manifest['devDependencies']['typescript'] != PINS['typescript']:
        raise ValueError('Angular/TypeScript: toolchain pin drift')
    if ('go ' + PINS['go']) not in (root/'services/platform/go.mod').read_text().splitlines():
        raise ValueError('go: module pin drift')
    rust=(root/'rust-toolchain.toml').read_text()
    if re.search(r'^channel\s*=\s*"([^"]+)"',rust,re.M)[1]!=PINS['rust']:
        raise ValueError('rust: toolchain pin drift')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bootstrap',action='store_true',help='Check Python and Node before installing dependencies')
    parser.add_argument('--exact',action='store_true',help='Require the reproducible CI versions')
    args=parser.parse_args()
    try:
        check_pins(ROOT)
        commands={'python':[sys.executable,'--version'],'node':['node','--version']}
        if not args.bootstrap:
            portable_go=ROOT/'.tools'/('go'+PINS['go'])/'bin'/('go.exe' if sys.platform=='win32' else 'go')
            commands.update(go=[os.environ.get('VEYA_GO') or shutil.which('go') or str(portable_go),'version'],pnpm=['pnpm.cmd' if sys.platform=='win32' else 'pnpm','--version'],rust=['rustc','--version'],uv=['uv','--version'])
        for tool,command in commands.items():
            executable=shutil.which(command[0])
            if not executable: raise ValueError(f'{tool}: executable missing; install {PINS[tool]}')
            result=subprocess.run([executable,*command[1:]],capture_output=True,text=True,timeout=30,check=False)
            if result.returncode: raise ValueError(f'{tool}: version check failed; install {PINS[tool]}')
            print(f'{tool}: {validate_version(tool,result.stdout,exact=args.exact)}')
    except (ValueError,OSError,subprocess.TimeoutExpired) as error:
        parser.exit(1,str(error)+'\n')
    print('Toolchain requirements satisfied; dependency installation may proceed.')


if __name__=='__main__': main()
