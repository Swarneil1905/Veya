"""Readiness probe for the private team container; credentials never enter stdout."""

import os
import urllib.request


def main():
    token = os.environ.get('VEYA_TEAM_GATEWAY_TOKEN', '')
    if not token:
        raise SystemExit(1)
    request = urllib.request.Request(
        'http://127.0.0.1:8080/ready', headers={'Authorization': 'Bearer ' + token}
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status != 200:
                raise SystemExit(1)
    except Exception:
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
