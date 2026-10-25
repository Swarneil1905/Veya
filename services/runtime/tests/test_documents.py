import io
import zipfile

import pytest

from veya.domain.models import DomainError
from veya.ingestion.intake import validate
from veya.ingestion.pdf import extract_pdf
from veya.ingestion.tables import extract_table


def test_intake_rejects_disguises_encoding_and_archive_bombs():
    for name, data in [
        ('orders.csv', b'MZexecutable'),
        ('orders.csv', b'\xff\xfe'),
        ('orders.exe', b'a,b\n1,2'),
    ]:
        with pytest.raises(DomainError):
            validate(name, data)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', 'x' * 5_000_000)
    with pytest.raises(DomainError):
        validate('orders.xlsx', archive.getvalue())


def test_csv_retains_exact_values_and_cell_provenance():
    result = extract_table('csv', b'date,quantity,currency,amount\n2026-10-25,1.250,USD,12.30\n')
    cells = result['blocks']
    assert [(c['locator'], c['value'], c['value_type']) for c in cells] == [
        ('CSV!A2', '2026-10-25', 'date'),
        ('CSV!B2', '1.250', 'decimal'),
        ('CSV!C2', 'USD', 'currency'),
        ('CSV!D2', '12.30', 'decimal'),
    ]
    assert not result['issues']


def test_table_ambiguity_formula_and_invalid_rows_are_visible():
    result = extract_table('csv', b'amount,amount,date\n=SUM(A1),1,no-date\n2\n')
    assert {'ambiguous_headers', 'formula', 'invalid_date', 'row_width'} <= {
        x['code'] for x in result['issues']
    }
    assert result['blocks'][0]['text'] == '=SUM(A1)'
    assert result['blocks'][0]['value_type'] == 'untrusted_text'


def test_pdf_provenance_and_failures():
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject(
        {
            NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/Type1'),
            NameObject('/BaseFont'): NameObject('/Helvetica'),
        }
    )
    page[NameObject('/Resources')] = DictionaryObject(
        {NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 10 100 Td (Invoice total 12.30) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(stream)
    data = io.BytesIO()
    writer.write(data)
    result = extract_pdf(data.getvalue())
    from veya.ingestion.worker import extract

    assert extract('pdf', data.getvalue()) == result
    assert result['blocks'][0]['locator'] == 'page:1:block:1'
    assert result['blocks'][0]['text'] == 'Invoice total 12.30'
    writer.encrypt('password')
    encrypted = io.BytesIO()
    writer.write(encrypted)
    for raw in [b'%PDF-broken', encrypted.getvalue()]:
        with pytest.raises(DomainError):
            extract_pdf(raw)


from veya.ingestion.jobs import Documents
from veya.storage.sqlite import Database
from veya.storage.submission import submit


def test_durable_import_resume_dedup_versions_and_revoked_citation(tmp_path):
    db = Database(tmp_path)
    docs = Documents(db, 'tenant_local')
    first = docs.intake('request_a', 'orders.csv', b'amount\n12.30\n')
    assert first['state'] == 'queued'
    assert docs.detail(first['id'], process=False)['blocks'] == []
    resumed = Documents(Database(tmp_path), 'tenant_local')
    ready = resumed.process(first['id'])
    assert ready['state'] == 'ready'
    citation = ready['blocks'][0]['citation']
    assert resumed.citation(citation)['text'] == '12.30'
    duplicate = resumed.intake('request_b', 'orders.csv', b'amount\n12.30\n')
    assert duplicate['id'] == first['id']
    new = resumed.intake('request_c', 'orders.csv', b'amount\n45.60\n')
    assert new['version'] == 2
    assert resumed.citation(citation)['text'] == '12.30'
    assert len(resumed.versions(first['id'])) == 2
    resumed.revoke(first['id'])
    assert resumed.citation(citation)['available'] is False
    with pytest.raises(DomainError):
        resumed.detail(first['id'])
    with pytest.raises(DomainError):
        Documents(db, 'tenant_other').detail(new['id'])


def test_submission_binds_exact_documents_atomically(tmp_path):
    db = Database(tmp_path)
    docs = Documents(db, 'tenant_local')
    a = docs.intake('a', 'a.csv', b'amount\n12.30\n')
    with pytest.raises(DomainError):
        submit(db, 'tenant_local', 's', 'Task', 'Brief', document_ids=[a['id']])
    docs.process(a['id'])
    task, run, created = submit(db, 'tenant_local', 's', 'Task', 'Brief', document_ids=[a['id']])
    assert created and docs.for_task(task.id)[0]['id'] == a['id']
    assert not submit(db, 'tenant_local', 's', 'Task', 'Brief', document_ids=[a['id']])[2]
    with pytest.raises(DomainError):
        submit(db, 'tenant_local', 's', 'Task', 'Brief', document_ids=[])
    docs.revoke(a['id'])
    assert docs.for_task(task.id)[0]['state'] == 'revoked'
    with pytest.raises(DomainError):
        submit(db, 'tenant_local', 's2', 'Task', 'Brief', document_ids=[a['id']])


def test_failed_extraction_has_reason_and_retry_does_not_publish_partial_data(tmp_path):
    docs = Documents(Database(tmp_path), 'tenant_local')
    a = docs.intake('a', 'a.pdf', b'%PDF-broken')
    failed = docs.process(a['id'])
    assert failed['state'] == 'failed' and failed['error'] and not failed['blocks']
    assert docs.retry(a['id'])['state'] == 'queued'
    assert docs.detail(a['id'], process=False)['blocks'] == []


def test_xlsx_dates_decimals_and_formula_provenance():
    from datetime import date

    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = 'Orders'
    sheet.append(['date', 'quantity', 'currency', 'amount'])
    sheet.append([date(2026, 10, 25), 1.25, 'USD', '=1+2'])
    data = io.BytesIO()
    book.save(data)
    assert validate('orders.xlsx', data.getvalue()) == 'xlsx'
    result = extract_table('xlsx', data.getvalue())
    assert result['blocks'][0]['locator'] == 'Orders!A2'
    assert result['blocks'][0]['value'] == '2026-10-25'
    assert result['blocks'][1]['value'] == '1.25'
    assert result['blocks'][1]['value_type'] == 'decimal'
    assert result['issues'] == [{'code': 'formula', 'locator': 'Orders!D2'}]


def test_zip_paths_entities_and_links_are_rejected():
    cases = [
        ('../escape.xml', '<x/>'),
        ('xl/evil.xml', '<!DOCTYPE x [<!ENTITY a "secret">]><x>&a;</x>'),
        (
            'xl/_rels/workbook.xml.rels',
            '<Relationships><Relationship TargetMode="External" Target="https://example.com"/></Relationships>',
        ),
    ]
    for name, content in cases:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as z:
            z.writestr('[Content_Types].xml', '<Types/>')
            z.writestr('xl/workbook.xml', '<workbook/>')
            z.writestr(name, content)
        with pytest.raises(DomainError):
            validate('evil.xlsx', stream.getvalue())


def test_content_dedup_does_not_cross_tenants_or_restore_revoked_grant(tmp_path):
    db = Database(tmp_path)
    first = Documents(db, 'tenant_a')
    second = Documents(db, 'tenant_b')
    a = first.intake('request', 'file.csv', b'a\n1\n')
    first.process(a['id'])
    first.revoke(a['id'])
    with pytest.raises(DomainError):
        first.intake('request', 'file.csv', b'a\n1\n')
    b = first.intake('explicit_new_request', 'file.csv', b'a\n1\n')
    assert b['id'] != a['id'] and b['version'] == 2
    assert not first.citation(a['id'] + ':0')['available']
    other = second.intake('request', 'file.csv', b'a\n1\n')
    assert other['state'] == 'queued' and other['version'] == 1
    with pytest.raises(DomainError):
        first.intake('explicit_new_request', 'file.csv', b'a\n2\n')


def test_concurrent_imports_share_one_version(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    db = Database(tmp_path)

    def create(n):
        return Documents(db, 'tenant_a').intake('request_' + str(n), 'file.csv', b'a\n1\n')

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(create, range(8)))
    assert len({r['id'] for r in results}) == 1


def test_expired_extraction_lease_fences_late_publication(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    import veya.ingestion.jobs as jobs

    db = Database(tmp_path)
    docs = Documents(db, 'tenant_a')
    item = docs.intake('r', 'a.csv', b'a\n1\n')
    started, finish = Event(), Event()

    def slow(kind, content):
        started.set()
        assert finish.wait(5)
        return {'blocks': [{'locator': 'CSV!A2', 'text': 'late'}], 'issues': []}

    monkeypatch.setattr(jobs, 'extract', slow)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(docs.process, item['id'])
        assert started.wait(5)
        assert docs.detail(item['id'])['blocks'] == []
        assert docs.process(item['id'])['state'] == 'processing'
        with db.transaction() as c:
            c.execute('UPDATE document_extractions SET lease_until=0')
        monkeypatch.setattr(
            jobs,
            'extract',
            lambda *_: {'blocks': [{'locator': 'CSV!A2', 'text': 'current'}], 'issues': []},
        )
        assert docs.process(item['id'])['blocks'][0]['text'] == 'current'
        finish.set()
        assert future.result()['blocks'][0]['text'] == 'current'


def test_revocation_while_parsing_prevents_publication_access(tmp_path, monkeypatch):
    import veya.ingestion.jobs as jobs

    docs = Documents(Database(tmp_path), 'tenant_a')
    item = docs.intake('r', 'a.csv', b'a\n1\n')

    def extract_and_revoke(*_):
        docs.revoke(item['id'])
        return {'blocks': [{'locator': 'CSV!A2', 'text': '1'}], 'issues': []}

    monkeypatch.setattr(jobs, 'extract', extract_and_revoke)
    with pytest.raises(DomainError):
        docs.process(item['id'])
    assert not docs.citation(item['id'] + ':0')['available']


def test_corrupted_original_never_resolves_as_valid_evidence(tmp_path):
    db = Database(tmp_path)
    docs = Documents(db, 'tenant_a')
    item = docs.intake('r', 'a.csv', b'a\n1\n')
    ready = docs.process(item['id'])
    with db.transaction() as c:
        c.execute('UPDATE documents SET content=? WHERE id=?', (b'changed', item['id']))
    assert not docs.citation(ready['blocks'][0]['citation'])['available']


def test_document_api_and_result_inspection(client, settings):
    import base64
    import json

    from veya.artifacts.store import ArtifactStore

    data = {
        'request_id': 'r',
        'name': 'orders.csv',
        'content': base64.b64encode(b'amount\n12.30\n').decode(),
    }
    response = client.post('/v1/documents', json=data)
    assert response.status_code == 200
    doc = response.json()
    ready = client.post('/v1/documents/' + doc['id'] + '/process').json()
    assert ready['state'] == 'ready'
    ref = ready['blocks'][0]['citation']
    submission = client.post(
        '/v1/tasks',
        json={
            'client_request_id': 's',
            'title': 'Review order',
            'instruction': 'Inspect evidence',
            'document_ids': [doc['id']],
        },
    )
    assert submission.status_code == 201
    task, run = submission.json()['task'], submission.json()['run']
    db = Database(settings.storage_root)
    artifact = ArtifactStore(db).put(
        settings.tenant_id,
        run['id'],
        json.dumps(
            {
                'claims': [{'text': 'Amount is 12.30', 'citations': [ref, 'doc_missing:0']}],
                'exceptions': ['Supplier needs confirmation'],
            }
        ).encode(),
        'result.json',
        'application/json',
    )
    page = client.get('/v1/runs/' + run['id'] + '/results').json()
    assert page['items'][0]['claims'][0]['citations'][0]['available']
    assert not page['items'][0]['claims'][0]['citations'][1]['available']
    assert page['items'][0]['exceptions'] == ['Supplier needs confirmation']
    assert client.get('/v1/citations/' + ref).json()['text'] == '12.30'
    assert client.get('/v1/tasks/' + task['id'] + '/documents').json()['items'][0]['blocks'] == []
    assert client.get('/v1/artifacts/' + artifact.id + '/download').status_code == 200
    assert client.post('/v1/documents/' + doc['id'] + '/revoke').status_code == 200
    assert not client.get('/v1/citations/' + ref).json()['available']
    assert client.get('/v1/documents/' + doc['id']).status_code == 404
    assert (
        client.get('/v1/tasks/' + task['id'] + '/documents').json()['items'][0]['state']
        == 'revoked'
    )


def test_document_api_rejects_paths_identity_injection_and_invalid_bytes(client):
    import base64

    valid = {'request_id': 'r', 'name': 'a.csv', 'content': base64.b64encode(b'a\n1\n').decode()}
    for patch in [
        {'name': '../a.csv'},
        {'content': '?'},
        {'tenant_id': 'other'},
        {'content': 'a' * 699056},
    ]:
        assert client.post('/v1/documents', json={**valid, **patch}).status_code == 422
    assert (
        client.post(
            '/v1/documents', json=valid, headers={'Authorization': 'Bearer wrong'}
        ).status_code
        == 401
    )


def test_versions_response_uses_boolean_revocation(client):
    import base64

    payload = {'request_id': 'v', 'name': 'a.csv', 'content': base64.b64encode(b'a\n1\n').decode()}
    item = client.post('/v1/documents', json=payload).json()
    reply = client.get('/v1/documents/' + item['id'] + '/versions')
    assert reply.status_code == 200
    assert reply.json()['items'][0]['revoked'] is False


def test_pdf_runlength_and_array_decompression_bombs_are_rejected():
    import zlib

    from pypdf import PdfWriter
    from pypdf.generic import ArrayObject, DictionaryObject, EncodedStreamObject, NameObject

    from veya.ingestion.worker import extract

    for kind in ['runlength', 'array', 'flate']:
        writer = PdfWriter()
        page = writer.add_blank_page(width=200, height=200)
        font = DictionaryObject(
            {
                NameObject('/Type'): NameObject('/Font'),
                NameObject('/Subtype'): NameObject('/Type1'),
                NameObject('/BaseFont'): NameObject('/Helvetica'),
            }
        )
        page[NameObject('/Resources')] = DictionaryObject(
            {NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})}
        )
        text = b'BT /F1 12 Tf 10 100 Td (Visible text) Tj ET'
        stream = EncodedStreamObject()
        if kind == 'runlength':
            stream[NameObject('/Filter')] = NameObject('/RunLengthDecode')
            stream._data = b'\x81 ' * 16385 + bytes([len(text) - 1]) + text + b'\x80'
        else:
            stream[NameObject('/Filter')] = NameObject('/FlateDecode')
            stream._data = zlib.compress(b' ' * (600000 if kind == 'array' else 2097152) + text)
        ref = writer._add_object(stream)
        page[NameObject('/Contents')] = ArrayObject([ref, ref]) if kind == 'array' else ref
        raw = io.BytesIO()
        writer.write(raw)
        assert validate('bomb.pdf', raw.getvalue()) == 'pdf'
        with pytest.raises(DomainError) as error:
            extract_pdf(raw.getvalue())
        from pypdf.errors import LimitReachedError

        assert isinstance(error.value.__cause__, LimitReachedError), kind
        with pytest.raises(DomainError):
            extract('pdf', raw.getvalue())
