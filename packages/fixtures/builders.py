"""Stable synthetic records, independent of wall time, randomness and call order."""

import hashlib
import json


class FixtureBuilder:
    def __init__(self, seed: str):
        if not isinstance(seed, str) or not seed.strip() or len(seed) > 200:
            raise ValueError("A bounded nonblank fixture seed is required")
        self.seed = seed

    def _id(self, kind: str, key: str) -> str:
        if not isinstance(key, str) or not key.strip() or len(key) > 200:
            raise ValueError("A bounded nonblank fixture key is required")
        data = json.dumps([self.seed, kind, key], separators=(",", ":")).encode()
        return "fixture_" + hashlib.sha256(data).hexdigest()[:32]

    def tenant(self) -> dict:
        return {
            "id": self._id("tenant", "root"),
            "name": "Synthetic workspace",
            "synthetic": True,
        }

    def _record(self, kind: str, key: str) -> dict:
        return {
            "id": self._id(kind, key),
            "tenant_id": self.tenant()["id"],
            "created_at": "2026-01-01T00:00:00+00:00",
            "synthetic": True,
        }

    def user(self, key: str) -> dict:
        return self._record("user", key) | {"name": key, "role": "reviewer"}

    def task(self, key: str) -> dict:
        return self._record("task", key) | {
            "title": key,
            "instruction": "Inspect synthetic evidence",
            "state": "queued",
            "schema_version": 1,
        }

    def document(self, key: str) -> dict:
        content = ("Synthetic document: " + key).encode()
        return self._record("document", key) | {
            "name": key + ".txt",
            "mime_type": "text/plain",
            "text": content.decode(),
            "sha256": hashlib.sha256(content).hexdigest(),
            "size": len(content),
        }
