"""Bounded parser subprocess; no workspace path, credential or environment inheritance."""

import json
import os
import subprocess
import sys
from pathlib import Path

from veya.domain.models import DomainError

MAX_RESULT = 262144


def extract(kind: str, content: bytes) -> dict:
    source = Path(__file__).resolve().parents[2]
    # Isolated interpreter; add only this installed/source package location explicitly.
    code = 'import sys; sys.path.insert(0, sys.argv[1]); from veya.ingestion.worker import main; main(sys.argv[2])'
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {'SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP'}
    }
    try:
        result = subprocess.run(
            [sys.executable, '-I', '-c', code, str(source), kind],
            input=content,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=8,
            env=env,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise DomainError(
            'invalid_input', 'Document parsing timed out or could not start'
        ) from error
    if result.returncode != 0 or len(result.stdout) > MAX_RESULT:
        raise DomainError(
            'invalid_input', 'Document could not be parsed within the extraction limits'
        )
    value = json.loads(result.stdout)
    if 'error' in value:
        raise DomainError('invalid_input', value['error'])
    return value


def main(kind: str) -> None:
    from veya.ingestion.email import extract_email
    from veya.ingestion.pdf import extract_pdf
    from veya.ingestion.tables import extract_table

    try:
        # Numeric limits plus a process deadline bound malformed parser work.
        from veya.ingestion.intake import MAX_BYTES

        content = sys.stdin.buffer.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise DomainError('too_large', 'Document exceeds 512 KiB')
        value = (
            extract_email(content)
            if kind == 'eml'
            else extract_pdf(content)
            if kind == 'pdf'
            else extract_table(kind, content)
        )
        encoded = json.dumps(value, ensure_ascii=True).encode()
        if len(encoded) > MAX_RESULT:
            raise DomainError('too_large', 'Extracted text exceeds 256 KiB')
    except DomainError as error:
        encoded = json.dumps({'error': str(error)}).encode()
    except Exception:
        encoded = b'{"error":"Document is malformed or uses unsupported features"}'
    sys.stdout.buffer.write(encoded)
