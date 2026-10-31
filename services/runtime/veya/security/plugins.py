"""Host-approved plugin identity. A manifest never grants its own capabilities."""

from dataclasses import dataclass
from pathlib import Path

from veya.domain.models import DomainError, identifier
from veya.security.artifact_integrity import verified_bytes


@dataclass(frozen=True)
class PluginApproval:
    id: str
    version: str
    sha256: str
    capabilities: frozenset[str]

    def load(self, path: Path, *, version: str, capabilities: frozenset[str]) -> bytes:
        identifier(self.id)
        if version != self.version or capabilities != self.capabilities:
            raise DomainError('forbidden', 'Plugin approval does not match its declaration')
        content = verified_bytes(path, self.sha256)
        if not content.startswith(b'\x00asm\x01\x00\x00\x00'):
            raise DomainError('forbidden', 'Only approved WebAssembly modules are supported')
        return content
