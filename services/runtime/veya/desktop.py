"""Go-owned private execution/storage server. Bootstrap secrets travel over an inherited pipe.

Closing the platform pipe requests graceful shutdown, including when the parent dies.
No model worker is started: submitted tasks remain durably queued.
"""

import json
import socket
import sys
import threading
from pathlib import Path

import uvicorn

from veya.api.app import create_app
from veya.config import Settings


def main():
    try:
        raw = sys.stdin.buffer.readline(16_385)
        if len(raw) > 16_384 or not raw.endswith(b'\n'):
            raise ValueError('Invalid bootstrap')
        config = json.loads(raw)
        if (
            set(config)
            not in (
                {'protocol', 'storage_root', 'session_token'},
                {'protocol', 'storage_root', 'session_token', 'reviewer_token'},
            )
            or type(config['protocol']) is not int
            or config['protocol'] != 1
            or not isinstance(config['session_token'], str)
            or not 32 <= len(config['session_token']) <= 256
        ):
            raise ValueError('Invalid bootstrap')
        reviewer = config.get('reviewer_token')
        if reviewer is not None and (
            not isinstance(reviewer, str)
            or not 32 <= len(reviewer) <= 256
            or reviewer == config['session_token']
        ):
            raise ValueError('Invalid reviewer credential')
        root = Path(config['storage_root'])
        if not root.is_absolute():
            raise ValueError('Absolute storage root required')
    except (ValueError, TypeError, KeyError):
        print(json.dumps({'status': 'failed', 'code': 'invalid_bootstrap'}), flush=True)
        return 1
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
            settings = Settings(
                'local', f'http://127.0.0.1:{port}', root, 'desktop', 'vault:desktop/session'
            )
            from veya.policy.host import local_inbox

            app = create_app(
                settings,
                config['session_token'],
                approval_inbox=local_inbox(root, settings.tenant_id) if reviewer else None,
                reviewer_token=reviewer,
            )

            class Server(uvicorn.Server):
                async def startup(self, sockets=None):
                    await super().startup(sockets)
                    if self.started:
                        print(
                            json.dumps({'status': 'ready', 'protocol': 1, 'port': port}), flush=True
                        )

            server = Server(
                uvicorn.Config(
                    app,
                    host='127.0.0.1',
                    port=port,
                    log_config=None,
                    access_log=False,
                    timeout_graceful_shutdown=3,
                )
            )

            def watch_parent():
                # No additional commands or unbounded reads accepted over this pipe.
                sys.stdin.buffer.read(1)
                server.should_exit = True

            threading.Thread(target=watch_parent, daemon=True).start()
            server.run(sockets=[listener])
        return 0
    except Exception:
        # Never print bootstrap, credential, document contents or traceback paths.
        print(json.dumps({'status': 'failed', 'code': 'runtime_start_failed'}), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
