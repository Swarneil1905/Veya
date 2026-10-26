"""Conservative document intake; never unpack archives onto the filesystem."""

import io
import zipfile
from pathlib import PurePosixPath

from defusedxml.ElementTree import fromstring

from veya.domain.models import DomainError

MAX_BYTES = 524288
MAX_EXPANDED = 4 * 1024 * 1024


def validate(name: str, content: bytes) -> str:
    if (
        not name
        or len(name) > 200
        or any(c in name for c in '/\\:')
        or any(ord(c) < 32 for c in name)
    ):
        raise DomainError('invalid_input', 'Use a file name without a path')
    if not content or len(content) > MAX_BYTES:
        raise DomainError('too_large', 'Choose a nonempty document up to 512 KiB')
    kind = name.rsplit('.', 1)[-1].lower()
    if content.startswith((b'MZ', b'\x7fELF', b'#!')):
        raise DomainError('invalid_input', 'Executable content is not a document')
    if kind == 'eml':
        from veya.ingestion.email import extract_email

        extract_email(content, validation_only=True)
        return kind
    if kind == 'pdf' and content.startswith(b'%PDF-'):
        return kind
    if kind == 'csv':
        try:
            text = content.decode('utf-8-sig')
        except UnicodeError as error:
            raise DomainError('invalid_input', 'CSV files must use UTF-8 encoding') from error
        if any(ord(c) < 32 and c not in '\t\r\n' for c in text):
            raise DomainError('invalid_input', 'CSV contains binary control characters')
        return kind
    if kind == 'xlsx' and content.startswith(b'PK\x03\x04'):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                entries = archive.infolist()
                if len(entries) > 256 or len({e.filename for e in entries}) != len(entries):
                    raise ValueError('archive entries')
                if sum(e.file_size for e in entries) > MAX_EXPANDED:
                    raise ValueError('expanded size')
                names = {e.filename for e in entries}
                if not {'[Content_Types].xml', 'xl/workbook.xml'} <= names:
                    raise ValueError('workbook required')
                for entry in entries:
                    path = PurePosixPath(entry.filename)
                    if (
                        path.is_absolute()
                        or '..' in path.parts
                        or '\\' in entry.filename
                        or entry.flag_bits & 1
                        or entry.file_size > 1024 * 1024
                        or entry.file_size > max(1, entry.compress_size) * 100
                        or 'vbaproject' in entry.filename.lower()
                        or 'externallinks' in entry.filename.lower()
                    ):
                        raise ValueError('unsafe archive')
                    data = archive.read(entry)
                    if entry.filename.endswith(('.xml', '.rels')):
                        node = fromstring(data)
                        if entry.filename.endswith('.rels') and any(
                            n.get('TargetMode') == 'External' for n in node
                        ):
                            raise ValueError('external workbook relationship')
            return kind
        except Exception as error:
            raise DomainError(
                'invalid_input', 'Workbook is malformed, oversized or contains unsafe links'
            ) from error
    raise DomainError('invalid_input', 'Choose a text PDF, UTF-8 CSV XLSX workbook or EML message')
