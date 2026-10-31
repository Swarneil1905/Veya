import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3]))
from packages.connectors.tests.contract_suite import check_adapter
from packages.contributor_kit.fixtures import sample
from scripts.audit_repository_rules import assess
from scripts.build_manifest import LOCKS, build
from training.data.export_trl import conversation, tokenize


def test_contributor_contracts_are_offline():
    checks = asyncio.run(check_adapter(*sample(), timeout=0.1))
    assert {'capability_denied', 'unknown_outcome', 'authentication'} <= set(checks)


def test_missing_repository_visibility_is_unknown_not_pass():
    expected = {
        'required_checks': ['Required quality gate'],
        'approving_reviews': 1,
        'protected_environments': ['release'],
    }
    report = assess(expected, None, {})
    assert not report['compliant'] and all(f['status'] == 'unknown' for f in report['findings'])
    report = assess(
        expected,
        {
            'required_status_checks': {'contexts': ['Required quality gate']},
            'required_pull_request_reviews': {'required_approving_review_count': 1},
            'enforce_admins': {'enabled': True},
        },
        {
            'release': {
                'protection_rules': [{'type': 'required_reviewers', 'reviewers': [{'id': 1}]}]
            }
        },
    )
    assert report['compliant']


def test_supply_chain_artifacts_bind_exact_locks_and_bytes(tmp_path):
    for name in LOCKS:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        content = 'lock fixture'
        if name.endswith('.lock'):
            content = '[[package]]\nname = "fixture"\nversion = "1.0.0"\n'
        if name.endswith('.yaml'):
            content = "lockfileVersion: '9.0'\npackages:\n  '@example/library@1.0.0':\n    resolution: {}\nsnapshots:\n"
        path.write_text(content)
    artifact = tmp_path / 'program.bin'
    artifact.write_bytes(b'first')
    manifest, sbom, provenance = build(tmp_path, [artifact], 'a' * 40, dirty=True)
    assert manifest['dirty'] and not manifest['signed']
    assert len(manifest['inputs']) == len(LOCKS) and len(sbom['components']) == 3
    assert provenance['subject'] == manifest['artifacts']
    artifact.write_bytes(b'changed')
    assert (
        build(tmp_path, [artifact], 'a' * 40, dirty=True)[0]['artifacts'] != manifest['artifacts']
    )
    with pytest.raises(ValueError):
        build(tmp_path, [artifact, artifact], 'a' * 40, dirty=True)


class ByteTokenizer:
    chat_template = 'fixture-only-json-chat-template-v1'

    @property
    def backend_tokenizer(self):
        return self

    def to_str(self):
        return 'fixture-only-utf8-byte-tokenizer-v1'

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt, **kwargs):
        value = json.dumps(messages, ensure_ascii=False)
        return list(value.encode()) if tokenize else value

    def decode(self, ids, **kwargs):
        return bytes(ids).decode()


def test_training_export_blocks_missing_tool_results_and_truncation():
    events = [
        {'sequence': 1, 'kind': 'start', 'content': 'Read invoice'},
        {
            'sequence': 2,
            'kind': 'proposal',
            'operation': 'read_invoice',
            'content': '{"id":"inv1"}',
        },
        {'sequence': 3, 'kind': 'tool', 'operation': 'read_invoice', 'content': '42 USD'},
        {'sequence': 4, 'kind': 'finish', 'content': 'Invoice total is 42 USD'},
    ]
    messages, _ = conversation({'events': events})
    assert messages[2]['tool_call_id'] == 'call_2'
    tokens, digest = tokenize(messages, ByteTokenizer(), max_tokens=1000)
    assert tokens and len(digest) == 64
    with pytest.raises(ValueError):
        tokenize(messages, ByteTokenizer(), max_tokens=32)
    with pytest.raises(ValueError):
        conversation({'events': events[:2] + events[3:]})
