"""Fail-closed scan of explicitly selected generated text/ZIP artifacts.

Not a general DLP classifier: encrypted/binary inputs require a pre-encryption
scan. Findings contain rule IDs and ordinal locations, never matched values.
"""

import argparse
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/runtime'))
from veya.privacy.scanning import MAX_BYTES, require_clean, scan_bytes  # noqa: E402,F401


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', type=Path, nargs='+')
    args = parser.parse_args()
    reports, failed = [], False
    for index, path in enumerate(args.paths):
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
                raise ValueError('Invalid scan selection')
            findings = scan_bytes(path.read_bytes(), archive=path.suffix.lower() == '.zip')
            reports.append(
                {'input': index, 'state': 'findings' if findings else 'clean', 'findings': findings}
            )
            failed |= bool(findings)
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, UnicodeError):
            reports.append({'input': index, 'state': 'scan_error'})
            failed = True
    print(json.dumps({'scanned': len(reports), 'reports': reports}))
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
