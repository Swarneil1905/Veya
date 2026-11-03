import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from packages.evals.retrieval.labels import label
from packages.evals.retrieval.runner import run as benchmark
from test_agent_execution import setup

from veya.domain.models import DomainError
from veya.ingestion.jobs import Documents
from veya.retrieval.context import assemble
from veya.retrieval.embeddings import Embeddings, lexical_embedding, vector
from veya.retrieval.hybrid import fuse, search
from veya.retrieval.rerank import rerank
from veya.storage.submission import submit
from veya.tools.read_only import ReadOnly


def test_embedding_resume_version_and_dimension_fences(tmp_path):
    db, _, task, _, doc = setup(tmp_path)
    calls = []

    def embed(text):
        calls.append(text)
        return [1.0, 2.0]

    index = Embeddings(db, 't', 'model-revision-1', 2, embed)
    assert index.index(doc['id'])['reused'] == 0
    assert index.index(doc['id'])['reused'] == 1
    assert len(calls) == 1
    assert Embeddings(db, 't', 'model-revision-2', 2, embed).index(doc['id'])['reused'] == 0
    with pytest.raises(DomainError, match='dimensions'):
        Embeddings(db, 't', 'model-revision-1', 3, lambda _: [1, 2, 3]).index(doc['id'])
    with pytest.raises(DomainError):
        search(db, 't', task.id, 'amount', query_vector=[1], dimensions=2)


def test_partial_embedding_failure_is_retryable_and_not_searchable(tmp_path):
    db, _, _, _, _ = setup(tmp_path)
    docs = Documents(db, 't')
    doc = docs.intake('two', 'two.csv', b'name,amount\nAcme,42\n')
    docs.process(doc['id'])
    calls = []

    def failing(text):
        calls.append(text)
        if len(calls) == 2:
            raise TimeoutError('provider interrupted')
        return [1, 0]

    with pytest.raises(TimeoutError):
        Embeddings(db, 't', 'partial', 2, failing).index(doc['id'])
    with db.connection() as c:
        assert (
            c.execute('SELECT state FROM retrieval_indexes WHERE model=?', ('partial',)).fetchone()[
                0
            ]
            == 'failed'
        )
    result = Embeddings(db, 't', 'partial', 2, lambda _: [1, 0]).index(doc['id'])
    assert result['reused'] == 1 and result['chunks'] == 2


@pytest.mark.parametrize(
    'value,dimensions',
    [([0, 0], 2), ([float('nan')], 1), ([True], 1), ([1], 2), ([float('inf')], 1)],
)
def test_invalid_vectors_rejected(value, dimensions):
    with pytest.raises(DomainError):
        vector(value, dimensions)


def test_real_task_search_context_and_revoke_propagation(tmp_path):
    db, _, task, _, doc = setup(tmp_path)
    Embeddings(db, 't').index(doc['id'])
    result = search(db, 't', task.id, '12.30', query_vector=lexical_embedding('12.30'))
    assert result['status'] == 'evidence'
    assert result['items'][0]['citation'] == doc['id'] + ':0'
    context = assemble(db, 't', task.id, result['items'], 1000)
    assert json.loads(context['payload'])['kind'] == 'untrusted_evidence'
    assert context['tokens'] <= 1000
    tiny = assemble(db, 't', task.id, result['items'], 64)
    assert tiny['records'] == [] and tiny['skipped']
    assert ReadOnly(db, 't', task.id).invoke('search_evidence', {'query': '12.30'})['records']
    Documents(db, 't').revoke(doc['id'])
    assert not search(db, 't', task.id, '12.30', query_vector=lexical_embedding('12.30'))['items']
    assert assemble(db, 't', task.id, result['items'], 1000)['records'] == []
    with db.connection() as c:
        assert c.execute('SELECT COUNT(*) FROM retrieval_indexes').fetchone()[0] == 0


def test_attachment_tenant_and_future_policy_filters(tmp_path):
    db, _, task, _, doc = setup(tmp_path)
    other, _, _ = submit(db, 'other', 's', 'Other', '12.30')
    empty, _, _ = submit(db, 't', 'empty', 'Empty', '12.30')
    assert search(db, 'other', other.id, '12.30')['status'] == 'no_evidence'
    assert search(db, 't', empty.id, '12.30')['status'] == 'no_evidence'
    with pytest.raises(DomainError):
        search(db, 'other', task.id, '12.30')
    with db.transaction() as c:
        c.execute(
            'UPDATE documents SET effective_at=? WHERE id=?',
            ((datetime.now(timezone.utc) + timedelta(days=1)).isoformat(), doc['id']),
        )
    assert not search(db, 't', task.id, '12.30')['items']


def test_new_source_version_requires_new_checkpoint(tmp_path):
    db, _, _, _, doc = setup(tmp_path)
    Embeddings(db, 't').index(doc['id'])
    docs = Documents(db, 't')
    changed = docs.intake('change', 'Invoice.csv', b'amount\n900\n')
    docs.process(changed['id'])
    task, _, _ = submit(db, 't', 'v2', 'New version', '900', document_ids=[changed['id']])
    assert not search(
        db, 't', task.id, '900', mode='vector', query_vector=lexical_embedding('900')
    )['items']
    Embeddings(db, 't').index(changed['id'])
    items = search(db, 't', task.id, '900', mode='vector', query_vector=lexical_embedding('900'))[
        'items'
    ]
    assert items and all(i['version'] == 2 and i['text'] == '900' for i in items)


def test_reranker_timeout_bad_scores_and_identity():
    items = [{'id': 'a', 'text': 'A', 'score': 1}, {'id': 'b', 'text': 'B', 'score': 2}]

    async def scenario():
        async def scores(*_):
            return [0, 2]

        async def bad(*_):
            return [float('nan'), 1]

        async def slow(*_):
            await asyncio.sleep(1)

        assert (await rerank('q', items))['status'] == 'disabled'
        assert [i['id'] for i in (await rerank('q', items, scores))['items']] == ['b', 'a']
        for scorer in (bad, slow):
            result = await rerank('q', items, scorer, timeout=0.01)
            assert result == {'items': items, 'status': 'fallback', 'reason': 'reranker_failed'}

    asyncio.run(scenario())
    assert len(fuse([[items[0], items[0]], [items[1]]])) == 2


@pytest.mark.parametrize(
    'expected,candidates,context,citations,correct,permitted,outcome',
    [
        (['a'], [], [], [], True, ['a'], 'missed_evidence'),
        (['a'], ['a'], [], [], True, ['a'], 'context_omission'),
        (['a'], ['a'], ['a'], [], True, ['a'], 'unsupported_answer'),
        (['a'], ['a'], ['a'], ['a'], False, ['a'], 'generation_failure'),
        (['a'], ['a'], ['a'], ['a'], True, ['a'], 'grounded_success'),
        (['a'], ['a', 'b'], ['a'], ['a'], True, ['a'], 'permission_failure'),
    ],
)
def test_failure_labels(expected, candidates, context, citations, correct, permitted, outcome):
    assert (
        label(
            expected=expected,
            candidates=candidates,
            context=context,
            citations=citations,
            answer_correct=correct,
            permitted=permitted,
        )
        == outcome
    )


def test_benchmark_records_versions_denominators_and_leakage():
    cases = [
        {'id': 'q1', 'family': 'invoice', 'query': 'amount', 'expected': ['a'], 'permitted': ['a']}
    ]

    def retrieve(query, mode):
        return {'items': [{'id': 'a'}]}

    report = benchmark(
        cases, retrieve, corpus_revision='c1', model_revision='m1', query_revision='q1'
    )
    assert report['clean'] and report['denominator'] == 6 and len(report['query_digest']) == 64
    leaked = benchmark(
        cases,
        retrieve,
        corpus_revision='c1',
        model_revision='m1',
        query_revision='q1',
        training_families=['invoice'],
    )
    assert not leaked['clean'] and leaked['leaked_families'] == ['invoice']
    duplicate_query = benchmark(
        cases,
        retrieve,
        corpus_revision='c1',
        model_revision='m1',
        query_revision='q1',
        training_queries=[' AMOUNT '],
    )
    assert not duplicate_query['clean'] and duplicate_query['leaked_queries'] == ['q1']


def test_revoke_during_embedding_cannot_publish_late_index(tmp_path):
    db, _, _, _, doc = setup(tmp_path)

    def revoke_while_embedding(text):
        Documents(db, 't').revoke(doc['id'])
        return [1, 0]

    with pytest.raises(DomainError):
        Embeddings(db, 't', 'revocation_race', 2, revoke_while_embedding).index(doc['id'])
    with db.connection() as c:
        assert (
            c.execute(
                'SELECT COUNT(*) FROM retrieval_indexes WHERE document_id=?', (doc['id'],)
            ).fetchone()[0]
            == 0
        )
        assert (
            c.execute(
                'SELECT COUNT(*) FROM retrieval_vectors WHERE model=?', ('revocation_race',)
            ).fetchone()[0]
            == 0
        )


def test_superseded_index_cannot_overwrite_newer_generation(tmp_path):
    db, _, _, _, doc = setup(tmp_path)

    def concurrent_index(text):
        Embeddings(db, 't', 'concurrent', 2, lambda _: [0, 1]).index(doc['id'])
        return [1, 0]

    with pytest.raises(DomainError, match='superseded'):
        Embeddings(db, 't', 'concurrent', 2, concurrent_index).index(doc['id'])
    with db.connection() as c:
        row = c.execute(
            'SELECT generation,state FROM retrieval_indexes WHERE model=?', ('concurrent',)
        ).fetchone()
        assert row['generation'] == 2 and row['state'] == 'ready'
