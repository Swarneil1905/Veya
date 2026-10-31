import base64
import io

import pytest
from fastapi.testclient import TestClient

from veya.api.app import create_app
from veya.domain.models import DomainError
from veya.extraction.invoice import extract_fields
from veya.ingestion.ocr import normalize_regions
from veya.ingestion.worker import extract


def test_low_confidence_and_conflicting_fields_require_review():
    result = normalize_regions(
        [([[0, 0], [100, 0], [100, 30], [0, 30]], 'Total: 42 USD', 0.65)], 1, 200, 200
    )
    assert result['issues'][0]['code'] == 'low_ocr_confidence'
    blocks = [{**b, 'citation': 'doc:0'} for b in result['blocks']]
    blocks.append({'text': 'Payable in EUR', 'locator': 'page:2', 'citation': 'doc:1'})
    fields = {f['name']: f for f in extract_fields({'blocks': blocks})}
    assert fields['total']['original'] == '42'
    assert fields['total']['reason'] == 'low_confidence'
    assert fields['currency']['original'] is None
    assert fields['vendor']['reason'] == 'missing'
    with pytest.raises(DomainError):
        normalize_regions([([[0, 0]] * 4, 'bad', float('nan'))], 1, 10, 10)


def test_authenticated_field_review_preserves_original_and_revision(client, settings):
    content = b'From: invoices@example.test\nDate: Fri, 30 Oct 2026 12:00:00 +0000\nSubject: Invoice\nContent-Type: text/plain\n\nVendor: Acme\nInvoice: INV-7\nTotal: 42 USD\nAlso payable EUR\n'
    doc = client.post(
        '/v1/documents',
        json={
            'request_id': 'review_doc',
            'name': 'invoice.eml',
            'content': base64.b64encode(content).decode(),
        },
    ).json()
    assert client.post('/v1/documents/' + doc['id'] + '/process').status_code == 200
    path = '/v1/documents/' + doc['id'] + '/fields'
    original = client.get(path).json()
    assert original['revision'] == 0
    payload = {
        'revision': 0,
        'values': {'vendor': 'Acme', 'invoice_number': 'INV-7', 'total': '43', 'currency': 'USD'},
        'note': 'Verified invoice total and selected USD against source.',
    }
    assert client.post(path, json={**payload, 'reviewer': 'forged'}).status_code == 422
    assert (
        client.post(
            path, json={**payload, 'values': {**payload['values'], 'total': ''}}
        ).status_code
        == 422
    )
    result = client.post(path, json=payload)
    assert result.status_code == 200, result.text
    total = next(f for f in result.json()['fields'] if f['name'] == 'total')
    assert total['original'] == '42' and total['value'] == '43' and total['evidence']
    assert total['reviewer'] == 'workspace_operator'
    assert client.post(path, json=payload).status_code == 409
    assert client.get(path, headers={'Authorization': 'Bearer invalid'}).status_code == 401
    with TestClient(
        create_app(settings, 'fixture-token-is-only-for-tests-00001'),
        headers={'Authorization': 'Bearer fixture-token-is-only-for-tests-00001'},
    ) as restarted:
        assert restarted.get(path).json()['revision'] == 1
    client.post('/v1/documents/' + doc['id'] + '/revoke')
    assert client.get(path).status_code == 404


def test_actual_scanned_invoice_ocr():
    pytest.importorskip('rapidocr_onnxruntime')
    pytest.importorskip('pypdfium2')
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new('RGB', (1000, 600), 'white')
    draw = ImageDraw.Draw(image)
    # Pillow's bundled font is available on every supported test OS.
    font = ImageFont.load_default(size=36)
    draw.multiline_text(
        (60, 60),
        'INVOICE\nVendor: Acme\nInvoice: INV-42\nTotal: 125 USD',
        font=font,
        fill='black',
        spacing=28,
    )
    data = io.BytesIO()
    image.save(data, format='PDF', resolution=144)
    image.close()
    result = extract('pdf', data.getvalue())
    text = ' '.join(b['text'] for b in result['blocks'])
    assert '125' in text and 'Acme' in text, text
    assert all(b['region'] and 0 <= b['confidence'] <= 1 for b in result['blocks'])
