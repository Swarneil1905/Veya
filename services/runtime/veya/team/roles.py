"""Server-owned workspace membership, never capabilities supplied by a document."""

from dataclasses import dataclass

from veya.domain.models import identifier

CAPABILITIES = {
    'operator': frozenset({'read', 'submit'}),
    'reviewer': frozenset({'read', 'review'}),
    'admin': frozenset({'read', 'submit', 'review', 'manage'}),
}


@dataclass(frozen=True)
class Membership:
    tenant: str
    subject: str
    role: str

    def __post_init__(self):
        identifier(self.tenant)
        if not isinstance(self.subject, str) or not 1 <= len(self.subject) <= 255:
            raise ValueError('A bounded identity-provider subject is required')
        if self.role not in CAPABILITIES:
            raise ValueError('Unknown workspace role')

    def require(self, capability: str):
        if capability not in CAPABILITIES[self.role]:
            raise PermissionError('Workspace role does not permit this operation')
