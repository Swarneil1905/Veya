import asyncio

import pytest
from test_proposals import setup_store

from veya.policy.egress import (
    ClassifiedField,
    Destination,
    EgressGateway,
    EgressGrant,
    EgressPolicy,
)
from veya.policy.engine import Actor, Classification, PolicyDenied


def test_destination_receives_only_allowlisted_fields(tmp_path):
    db, _, _ = setup_store(tmp_path)
    actor = Actor('reviewer', 'fixture_acme', 'workspace_1')
    destination = Destination('provider', 'https://fixture.invalid/v1', True)
    grant = EgressGrant(
        actor, destination, frozenset({'title'}), frozenset(), frozenset({Classification.PUBLIC})
    )
    policy = EgressPolicy('policy_1', (grant,))
    packets = []

    async def transport(packet):
        packets.append(packet)
        return {'ok': True}

    gateway = EgressGateway(
        db, lambda: policy, ((destination, transport),), max_bytes=4096, timeout=1
    )
    asyncio.run(
        gateway.send(
            actor,
            'provider',
            {
                'title': ClassifiedField('invoice', Classification.PUBLIC),
                'private': ClassifiedField('secret', Classification.RESTRICTED),
            },
            (),
        )
    )
    assert packets[0].fields == {'title': 'invoice'} and packets[0].attachments == ()


from dataclasses import replace

from veya.artifacts.store import ArtifactStore
from veya.domain.models import DomainError
from veya.policy.egress import ArtifactClassifications
from veya.storage.sqlite import Database


def fixture(tmp_path, classification=Classification.RESTRICTED):
    db, _, _ = setup_store(tmp_path)
    actor = Actor('reviewer', 'fixture_acme', 'workspace_1')
    artifact = ArtifactStore(db).put(
        actor.tenant_id, 'run_plan', b'fixture document', 'invoice.txt', 'text/plain'
    )
    if classification is not None:
        ArtifactClassifications(db).classify(actor.tenant_id, artifact.id, classification)
    local = Destination('local', 'http://127.0.0.1:9000', False)
    remote = Destination('remote', 'https://fixture.invalid/v1', True)
    grants = tuple(
        EgressGrant(
            actor, d, frozenset({'text'}), frozenset({artifact.id}), frozenset(Classification)
        )
        for d in (local, remote)
    )
    policies = [EgressPolicy('v1', grants)]
    packets = []

    async def transport(packet):
        packets.append(packet)
        return {'ok': True}

    gateway = EgressGateway(
        db,
        lambda: policies[0],
        ((local, transport), (remote, transport)),
        max_bytes=4096,
        timeout=1,
    )
    return db, actor, artifact, policies, gateway, packets


def test_restricted_document_cannot_escape_through_remote_fallback(tmp_path):
    db, actor, artifact, _, gateway, packets = fixture(tmp_path)
    asyncio.run(gateway.send(actor, 'local', {}, (artifact.id,)))
    with pytest.raises(PolicyDenied):
        asyncio.run(gateway.send(actor, 'remote', {}, (artifact.id,)))
    assert len(packets) == 1 and packets[0].attachments[0][1] == b'fixture document'
    assert (
        ArtifactClassifications(Database(tmp_path)).get(actor.tenant_id, artifact.id)
        == Classification.RESTRICTED
    )
    with pytest.raises(DomainError):
        ArtifactClassifications(db).classify(actor.tenant_id, artifact.id, Classification.PUBLIC)


@pytest.mark.parametrize(
    'case',
    [
        'unknown',
        'actor',
        'workspace',
        'tenant',
        'destination',
        'attachment',
        'restricted_field',
        'unknown_field',
        'unclassified',
        'oversize',
    ],
)
def test_denials_never_call_transport(tmp_path, case):
    db, actor, artifact, policies, gateway, packets = fixture(
        tmp_path, None if case == 'unknown' else Classification.PUBLIC
    )
    destination, fields, artifacts = 'remote', {}, (artifact.id,)
    if case == 'actor':
        actor = replace(actor, id='other')
    elif case == 'workspace':
        actor = replace(actor, workspace_id='other')
    elif case == 'tenant':
        actor = replace(actor, tenant_id='other')
    elif case == 'destination':
        destination = 'unregistered'
    elif case == 'attachment':
        artifacts = ('other',)
    elif case == 'restricted_field':
        fields = {'text': ClassifiedField('private', Classification.RESTRICTED)}
    elif case == 'unknown_field':
        fields = {'text': ClassifiedField('private', None)}
    elif case == 'unclassified':
        fields = {'text': 'raw unclassified'}
    elif case == 'oversize':
        fields = {'text': ClassifiedField('x' * 5000, Classification.PUBLIC)}
    with pytest.raises(DomainError):
        asyncio.run(gateway.send(actor, destination, fields, artifacts))
    assert not packets


def test_corrupt_artifact_and_policy_revocation_block_transmission(tmp_path):
    db, actor, artifact, policies, gateway, packets = fixture(tmp_path, Classification.PUBLIC)
    original = gateway._prepare

    def revoked(*args):
        prepared = original(*args)
        policies[0] = replace(policies[0], version='v2', grants=())
        return prepared

    gateway._prepare = revoked
    with pytest.raises(PolicyDenied):
        asyncio.run(gateway.send(actor, 'remote', {}, (artifact.id,)))
    assert not packets
    gateway._prepare = original
    # Restore the original exact grant from the policy captured by prepare.
    policies[0] = EgressPolicy(
        'v1',
        (
            EgressGrant(
                actor,
                Destination('remote', 'https://fixture.invalid/v1', True),
                frozenset(),
                frozenset({artifact.id}),
                frozenset({Classification.PUBLIC}),
            ),
        ),
    )
    ArtifactStore(db)._path(artifact).write_bytes(b'altered')
    with pytest.raises(DomainError):
        asyncio.run(gateway.send(actor, 'remote', {}, (artifact.id,)))
    assert not packets


def test_same_destination_id_with_changed_endpoint_is_not_authorized(tmp_path):
    db, actor, _, policies, _, packets = fixture(tmp_path, Classification.PUBLIC)

    async def transport(packet):
        packets.append(packet)
        return {}

    changed = Destination('remote', 'https://elsewhere.invalid', True)
    gateway = EgressGateway(
        db, lambda: policies[0], ((changed, transport),), max_bytes=4096, timeout=1
    )
    with pytest.raises(PolicyDenied):
        asyncio.run(gateway.send(actor, 'remote', {}, ()))
    assert not packets


@pytest.mark.parametrize(
    'url,remote',
    [
        ('http://fixture.invalid', True),
        ('https://fixture.invalid', False),
        ('https://user:secret@fixture.invalid', True),
        ('https://fixture.invalid?token=secret', True),
    ],
)
def test_destination_validation(url, remote):
    with pytest.raises(ValueError):
        Destination('bad', url, remote)
