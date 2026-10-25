"""Offline verifier. Keep the manifest SHA-256 separately from the bundle."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

MAX_BUNDLE = 40 * 1024 * 1024


def verify(data: bytes, expected_manifest_sha256: str) -> bool:
    try:
        if len(data) > MAX_BUNDLE or not re.fullmatch(
            r"[0-9a-f]{64}", expected_manifest_sha256
        ):
            return False
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if (
                len(names) != len(set(names))
                or len(names) > 34
                or sum(i.file_size for i in infos) > MAX_BUNDLE
            ):
                return False
            manifest = archive.read("manifest.json")
            if (
                len(manifest) > 65536
                or hashlib.sha256(manifest).hexdigest() != expected_manifest_sha256
            ):
                return False
            metadata = json.loads(manifest)
            if metadata["format_version"] != 1 or set(names) != set(
                metadata["members"]
            ) | {"manifest.json"}:
                return False
            for name, expected in metadata["members"].items():
                if name != "audit.json" and not re.fullmatch(
                    r"artifacts/[a-zA-Z0-9_-]{1,64}", name
                ):
                    return False
                content = archive.read(name)
                if (
                    len(content) != expected["size"]
                    or hashlib.sha256(content).hexdigest() != expected["sha256"]
                ):
                    return False
            for row in json.loads(archive.read("audit.json")):
                if row["tenant_id"] != metadata["tenant_id"]:
                    return False
                envelope = json.dumps(
                    [
                        row["tenant_id"],
                        row["sequence"],
                        row["previous_hash"],
                        row["payload_json"],
                    ],
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                )
                if hashlib.sha256(envelope.encode()).hexdigest() != row["entry_hash"]:
                    return False
        return True
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile, RuntimeError):
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    with args.bundle.open("rb") as stream:
        data = stream.read(MAX_BUNDLE + 1)
    if not verify(data, args.sha256):
        parser.exit(1, "FAIL: bundle integrity or retained digest mismatch\n")
    print("PASS: selected evidence matches the retained manifest digest")
