"""Fail-closed scan of explicitly selected generated text/ZIP artifacts.

Not a general DLP classifier: encrypted/binary inputs require a pre-encryption
scan. Findings contain rule IDs and ordinal locations, never matched values.
"""

import io
import re
import zipfile

MAX_BYTES = 40 * 1024 * 1024
RULES = {
    'seeded_secret': re.compile(rb'VEYA_SECRET_SENTINEL_[A-Za-z0-9_-]+'),
    'private_key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'github_token': re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})'),
    'provider_key': re.compile(rb'sk-(?:proj-)?[A-Za-z0-9_-]{24,}'),
    'credential_field': re.compile(
        rb'(?i)["\']?(?:password|api_key|access_token|authorization)["\']?\s*[:=]\s*["\'](?:Bearer )?[^"\'\s]{8,}["\']'
    ),
}


def scan_bytes(data: bytes, *, sentinels=(), archive=False):
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ValueError('Scan input exceeds limit')
    if any(not isinstance(s, bytes) or len(s) < 8 for s in sentinels):
        raise ValueError('Sentinels must be explicit byte strings of at least eight bytes')
    if archive:
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            entries = bundle.infolist()
            if not entries or len(entries) > 256 or sum(e.file_size for e in entries) > MAX_BYTES:
                raise ValueError('Archive scan bounds exceeded')
            findings: list[dict] = []
            for index, entry in enumerate(entries):
                if entry.is_dir():
                    continue
                if entry.flag_bits & 1 or entry.filename.lower().endswith(('.zip', '.gz', '.7z')):
                    raise ValueError('Encrypted or nested archive cannot be certified')
                findings.extend(
                    dict(f, member=index)
                    for f in scan_bytes(bundle.read(entry), sentinels=sentinels)
                )
            return findings
    # Reject binary data rather than silently declaring it clean.
    data.decode('utf-8', errors='strict')
    if b'\x00' in data:
        raise ValueError('Binary input requires a supported decoder')
    result = [{'rule': rule} for rule, pattern in RULES.items() if pattern.search(data)]
    if any(value in data for value in sentinels):
        result.append({'rule': 'configured_sentinel'})
    return result


def require_clean(data, *, archive=False):
    if scan_bytes(data, archive=archive):
        raise ValueError('Generated artifact failed secret policy')
