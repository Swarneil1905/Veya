"""Bounded parser subprocess; no workspace path, credential or environment inheritance."""

import json
import sys
import tempfile
from pathlib import Path

from veya.domain.models import DomainError
from veya.security.process import run_worker

MAX_RESULT = 262144


def extract(kind: str, content: bytes) -> dict:
    source = Path(__file__).resolve().parents[2]
    # Isolated interpreter; add only this installed/source package location explicitly.
    code = 'import sys; sys.path.insert(0, sys.argv[1]); from veya.ingestion.worker import main; main(sys.argv[2])'
    try:
        with tempfile.TemporaryDirectory(prefix='veya-parser-') as folder:
            output = run_worker(
                [sys.executable, '-I', '-c', code, str(source), kind],
                content,
                cwd=Path(folder),
                timeout=30 if kind == 'pdf' else 8,
                maximum=MAX_RESULT,
            )
    except DomainError as error:
        raise DomainError(
            'invalid_input', 'Document parsing timed out or could not start'
        ) from error
    value = json.loads(output)
    if 'error' in value:
        raise DomainError('invalid_input', value['error'])
    return value


def main(kind: str) -> None:
    try:
        # Numeric limits plus a process deadline bound malformed parser work.
        from veya.ingestion.intake import MAX_BYTES

        content = sys.stdin.buffer.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise DomainError('too_large', 'Document exceeds 512 KiB')
        if kind == 'eml':
            from veya.ingestion.email import extract_email

            value = extract_email(content)
        elif kind == 'pdf':
            from veya.ingestion.pdf import extract_pdf

            value = extract_pdf(content)
        else:
            from veya.ingestion.tables import extract_table

            value = extract_table(kind, content)
        encoded = json.dumps(value, ensure_ascii=True).encode()
        if len(encoded) > MAX_RESULT:
            raise DomainError('too_large', 'Extracted text exceeds 256 KiB')
    except DomainError as error:
        encoded = json.dumps({'error': str(error)}).encode()
    except Exception:
        encoded = b'{"error":"Document is malformed or uses unsupported features"}'
    sys.stdout.buffer.write(encoded)
