"""Run the local Angular/Go/Python workspace, without exposing a network listener."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--storage', type=Path, default=Path.home() / '.veya/web-workspace-v1')
    parser.add_argument('--python', default=os.environ.get('VEYA_PYTHON'))
    args = parser.parse_args()
    executable = ROOT / 'apps/desktop/src-tauri/binaries' / ('veya-platform.exe' if os.name == 'nt' else 'veya-platform')
    python = args.python or str(ROOT / 'services/runtime/.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python'))
    if not executable.is_file() or not (ROOT / 'apps/desktop/dist/index.html').is_file():
        parser.exit(1, 'Run pnpm build and pnpm build:platform first.\n')
    token = secrets.token_hex(32)
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    child = subprocess.Popen([str(executable), '--python', python, '--runtime', str(ROOT / 'services/runtime'), '--assets', str(ROOT / 'apps/desktop/dist')], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, creationflags=flags)
    try:
        child.stdin.write(json.dumps({'protocol': 1, 'storage_root': str(args.storage.resolve()), 'session_token': token}) + '\n')
        child.stdin.flush()
        ready = json.loads(child.stdout.readline())
        if ready.get('protocol') != 1 or ready.get('status') != 'ready':
            raise RuntimeError('Platform readiness failed')
        print('Local workspace connection link (private to this session):', flush=True)
        print(f'http://127.0.0.1:{ready["port"]}/#session={token}', flush=True)
        print('Keep this terminal open. Press Ctrl+C to stop. AI execution is not connected yet.', flush=True)
        child.wait()
    except KeyboardInterrupt:
        pass
    finally:
        child.stdin.close()
        try:
            child.wait(timeout=8)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


if __name__ == '__main__':
    main()
