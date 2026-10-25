"""Build/test the pinned Go platform. No downloads, commits, or publication."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='store_true')
    args = parser.parse_args()
    pin = json.loads((ROOT / 'toolchains.json').read_text())['go']
    portable = ROOT / '.tools' / ('go' + pin) / 'bin' / ('go.exe' if os.name == 'nt' else 'go')
    go = os.environ.get('VEYA_GO') or shutil.which('go') or (str(portable) if portable.is_file() else None)
    if not go:
        parser.exit(1, 'Install the Go version in toolchains.json or set VEYA_GO to its executable.\n')
    version = subprocess.check_output([go, 'version'], text=True)
    if f' go{pin} ' not in version:
        parser.exit(1, f'Go {pin} is required.\n')
    env = dict(os.environ, GOTOOLCHAIN='local')
    source = ROOT / 'services/platform'
    if args.test:
        subprocess.run([go, 'vet', './...'], cwd=source, env=env, check=True)
        # Race instrumentation requires a C compiler. CI runs it on Linux;
        # Windows local checks still exercise the same integration contracts.
        flags = ['-race'] if os.name != 'nt' else []
        subprocess.run([go, 'test', *flags, '-count=1', './...'], cwd=source, env=env, check=True)
    target = ROOT / 'apps/desktop/src-tauri/binaries'
    target.mkdir(parents=True, exist_ok=True)
    name = 'veya-platform.exe' if os.name == 'nt' else 'veya-platform'
    subprocess.run([go, 'build', '-trimpath', '-buildvcs=false', '-o', str(target / name), './cmd/veya-platform'], cwd=source, env=env, check=True)
    print(target / name)


if __name__ == '__main__':
    main()
