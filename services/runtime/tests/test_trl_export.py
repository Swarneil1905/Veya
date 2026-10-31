import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT))
from packages.fixtures.research import trace
from test_release_batch import ByteTokenizer
from test_research_data import review
from training.data.export_trl import export_trl, tokenizer_digest
from training.data.redact import Rule

from veya.research.models import TraceEvent
from veya.research.store import ResearchStore
from veya.storage.sqlite import Database


def fixture_export(tmp_path, tokenizer):
    store = ResearchStore(Database(tmp_path / 'workspace'), 'fixture_training')
    original = trace()
    start = original.events[0]
    events = (
        start,
        TraceEvent(
            **{
                **start.model_dump(),
                'sequence': 2,
                'kind': 'proposal',
                'operation': 'read_invoice',
                'effect': 'read',
                'content': json.dumps({'id': 'invoice_1'}),
            }
        ),
        TraceEvent(
            **{
                **start.model_dump(),
                'sequence': 3,
                'kind': 'tool',
                'operation': 'read_invoice',
                'effect': 'read',
                'content': '42 USD',
            }
        ),
        original.events[-1].model_copy(update={'sequence': 4}),
    )
    record = original.model_copy(update={'events': events})
    store.put(record)
    store.authorize('fixture_source', True)
    paths = set()

    def classify(value, path=''):
        if isinstance(value, dict):
            for key, child in value.items():
                classify(child, key if not path else path + '.' + key)
        elif isinstance(value, list):
            for child in value:
                classify(child, path + '[]')
        else:
            paths.add(path)

    classify(record.model_dump(mode='json'))
    rules = tuple(Rule(path=p, classification='public') for p in sorted(paths | {'reviewer'}))
    args = {
        'rules': rules,
        'held_out': (),
        'tokenizer': tokenizer,
        'tokenizer_revision': tokenizer_digest(tokenizer),
        'max_tokens': 2048,
    }
    output = tmp_path / 'train.jsonl'
    with pytest.raises(ValueError):
        export_trl(store, output, (record.id,), **args)
    assert not output.exists()
    review(store, record.id)
    result = export_trl(store, output, (record.id,), **args)
    assert result['rows'] == 1 and not result['trained']
    row = json.loads(output.read_text())
    assert row['messages'][1]['tool_calls'][0]['function']['arguments'] == {'id': 'invoice_1'}
    assert row['metadata']['synthetic'] is True
    with pytest.raises(FileExistsError):
        export_trl(store, output, (record.id,), **args)
    store.authorize('fixture_source', False)
    with pytest.raises(ValueError):
        export_trl(store, tmp_path / 'revoked.jsonl', (record.id,), **args)
    assert not (tmp_path / 'revoked.jsonl').exists()
    return result


def test_reviewed_training_export_preserves_tools_and_revocation(tmp_path):
    fixture_export(tmp_path, ByteTokenizer())


def test_real_qwen_tokenizer_export(tmp_path):
    transformers = pytest.importorskip('transformers')
    local = ROOT / 'artifacts/tokenizers/qwen2.5'
    if not (local / 'tokenizer.json').exists():
        pytest.skip('Local optional Qwen tokenizer validation files are not installed')
    tokenizer = transformers.AutoTokenizer.from_pretrained(
        local, local_files_only=True, trust_remote_code=False
    )
    assert hashlib.sha256((local / 'tokenizer.json').read_bytes()).hexdigest()
    fixture_export(tmp_path, tokenizer)
