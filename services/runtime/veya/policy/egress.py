"""Host-classified data -> exact destination policy -> bounded transport packet.

This gateway cannot sandbox arbitrary Python transports. Trusted adapters must
use the bound endpoint, enforce TLS/peer checks and reject redirects; fallback
must call send again for its own registered destination. No network client or
credentials are created here and no raw model-selected URL is accepted.
"""

import asyncio
import json
import math
from dataclasses import asdict, dataclass
from typing import Awaitable, Callable
from urllib.parse import urlsplit

from veya.artifacts.store import ArtifactStore
from veya.audit.ledger import AuditField, Sensitivity, append_in_transaction
from veya.domain.models import Artifact, DomainError, identifier
from veya.policy.engine import Actor, Classification, PolicyDenied
from veya.storage.sqlite import Database
from veya.tools.contracts import canonical_json
from veya.tools.retries import _bounded


@dataclass(frozen=True)
class Destination:
    id: str
    endpoint: str
    remote: bool

    def __post_init__(self):
        identifier(self.id)
        if (
            type(self.remote) is not bool
            or type(self.endpoint) is not str
            or len(self.endpoint) > 2048
        ):
            raise ValueError('Explicit destination profile and endpoint required')
        url = urlsplit(self.endpoint)
        if (
            any(ord(c) <= 32 for c in self.endpoint)
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or url.scheme not in {'http', 'https'}
        ):
            raise ValueError('Invalid credential-free destination')
        _ = url.port
        if self.remote and url.scheme != 'https':
            raise ValueError('Remote egress requires HTTPS')
        if not self.remote and url.hostname not in {'127.0.0.1', 'localhost', '::1'}:
            raise ValueError('Local egress requires loopback')


@dataclass(frozen=True)
class ClassifiedField:
    value: object
    classification: Classification | None


@dataclass(frozen=True)
class EgressGrant:
    actor: Actor
    destination: Destination
    fields: frozenset[str]
    artifact_ids: frozenset[str]
    classifications: frozenset[Classification]

    def __post_init__(self):
        if type(self.actor) is not Actor or type(self.destination) is not Destination:
            raise ValueError('Typed actor and destination required')
        for values in (self.fields, self.artifact_ids, self.classifications):
            if type(values) is not frozenset:
                raise ValueError('Egress grants must be immutable')
        for name in self.fields | self.artifact_ids:
            identifier(name)
        if not self.classifications or any(
            type(c) is not Classification for c in self.classifications
        ):
            raise ValueError('Known classifications required')


@dataclass(frozen=True)
class EgressPolicy:
    version: str
    grants: tuple[EgressGrant, ...]

    def __post_init__(self):
        identifier(self.version)
        if type(self.grants) is not tuple or any(type(g) is not EgressGrant for g in self.grants):
            raise ValueError('Immutable typed egress policy required')
        if len({(g.actor, g.destination.id) for g in self.grants}) != len(self.grants):
            raise ValueError('Ambiguous destination grants')

    def grant(self, actor, destination):
        for grant in self.grants:
            if grant.actor == actor and grant.destination == destination:
                return grant
        raise PolicyDenied('egress_destination')


@dataclass(frozen=True)
class Packet:
    destination: Destination
    fields_json: str
    attachments: tuple[tuple[Artifact, bytes], ...]

    @property
    def fields(self):
        return json.loads(self.fields_json)


class ArtifactClassifications:
    def __init__(self, db: Database):
        self.db = db

    def classify(self, tenant: str, artifact_id: str, classification: Classification):
        if type(classification) is not Classification:
            raise ValueError('Explicit artifact classification required')
        self.db.get_artifact(tenant, artifact_id)
        with self.db.transaction() as conn:
            row = conn.execute(
                'SELECT classification FROM artifact_classifications WHERE tenant_id=? AND artifact_id=?',
                (tenant, artifact_id),
            ).fetchone()
            if row:
                if row[0] != classification.value:
                    raise DomainError('conflict', 'Create a new artifact to change classification')
                return
            conn.execute(
                'INSERT INTO artifact_classifications VALUES (?,?,?)',
                (tenant, artifact_id, classification.value),
            )
            append_in_transaction(
                conn,
                tenant,
                'artifact.classified',
                {
                    'artifact_id': AuditField(artifact_id, Sensitivity.INTERNAL),
                    'classification': AuditField(classification.value, Sensitivity.INTERNAL),
                },
            )

    def get(self, tenant, artifact_id):
        with self.db.connection() as conn:
            row = conn.execute(
                'SELECT classification FROM artifact_classifications WHERE tenant_id=? AND artifact_id=?',
                (tenant, artifact_id),
            ).fetchone()
        if row is None:
            raise PolicyDenied('unknown_artifact_classification')
        return Classification(row[0])


class EgressGateway:
    def __init__(
        self,
        db: Database,
        policy: Callable[[], EgressPolicy],
        bindings: tuple[tuple[Destination, Callable[[Packet], Awaitable[dict]]], ...],
        *,
        max_bytes: int,
        timeout: float,
    ):
        if type(max_bytes) is not int or not 0 < max_bytes <= 1_048_576:
            raise ValueError('Configure an outbound byte limit at most 1 MiB')
        if (
            type(timeout) not in {int, float}
            or not math.isfinite(timeout)
            or not 0 < timeout <= 3600
        ):
            raise ValueError('Configure a bounded transport timeout')
        if type(bindings) is not tuple or not callable(policy):
            raise ValueError('Immutable bindings and current policy provider required')
        self.bindings: dict[str, tuple[Destination, Callable]] = {}
        for destination, transport in bindings:
            if (
                type(destination) is not Destination
                or not callable(transport)
                or destination.id in self.bindings
            ):
                raise ValueError('Each destination requires one trusted transport')
            self.bindings[destination.id] = (destination, transport)
        self.db, self.policy, self.max_bytes, self.timeout = db, policy, max_bytes, timeout

    @staticmethod
    def _allow(grant, classification):
        if (
            type(classification) is not Classification
            or classification not in grant.classifications
        ):
            raise PolicyDenied('egress_classification')
        if grant.destination.remote and classification == Classification.RESTRICTED:
            raise PolicyDenied('restricted_remote_egress')

    def _prepare(self, actor, destination, fields, artifact_ids):
        if type(actor) is not Actor or type(fields) is not dict or type(artifact_ids) is not tuple:
            raise PolicyDenied('invalid_egress_scope')
        if len(fields) > self.max_bytes or len(artifact_ids) > self.max_bytes:
            raise DomainError('too_large', 'Too many egress fields or attachments')
        policy = self.policy()
        grant = policy.grant(actor, destination)
        selected = {}
        for name, field in fields.items():
            identifier(name)
            if name not in grant.fields:
                continue
            if type(field) is not ClassifiedField:
                raise PolicyDenied('unknown_field_classification')
            self._allow(grant, field.classification)
            selected[name] = field.value
        encoded = canonical_json(selected, self.max_bytes)
        size, attachments = len(encoded.encode('utf-8')), []
        if (
            len(set(artifact_ids)) != len(artifact_ids)
            or not set(artifact_ids) <= grant.artifact_ids
        ):
            raise PolicyDenied('egress_attachment')
        for artifact_id in artifact_ids:
            self._allow(grant, ArtifactClassifications(self.db).get(actor.tenant_id, artifact_id))
            artifact, content = ArtifactStore(self.db).get(actor.tenant_id, artifact_id)
            size += len(content) + len(
                canonical_json(asdict(artifact), self.max_bytes).encode('utf-8')
            )
            if size > self.max_bytes:
                raise DomainError('too_large', 'Egress packet exceeds its configured byte limit')
            attachments.append((artifact, content))
        packet = Packet(destination, encoded, tuple(attachments))
        with self.db.transaction() as conn:
            append_in_transaction(
                conn,
                actor.tenant_id,
                'egress.authorized',
                {
                    'actor_id': AuditField(actor.id, Sensitivity.INTERNAL),
                    'workspace_id': AuditField(actor.workspace_id, Sensitivity.INTERNAL),
                    'destination_id': AuditField(destination.id, Sensitivity.INTERNAL),
                    'policy_version': AuditField(policy.version, Sensitivity.INTERNAL),
                },
            )
        return packet, policy, grant

    async def send(
        self,
        actor: Actor,
        destination_id: str,
        fields: dict[str, ClassifiedField],
        artifact_ids: tuple[str, ...],
    ) -> dict:
        binding = self.bindings.get(destination_id)
        if binding is None:
            raise PolicyDenied('egress_destination')
        destination, transport = binding
        packet, policy, grant = await asyncio.to_thread(
            self._prepare, actor, destination, fields, artifact_ids
        )

        async def invoke():
            current = self.policy()
            if current.version != policy.version or current.grant(actor, destination) != grant:
                raise PolicyDenied('egress_policy_changed')
            return await transport(packet)

        return await _bounded(invoke, self.timeout)
