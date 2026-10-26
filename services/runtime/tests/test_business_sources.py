from email.message import EmailMessage

import pytest

from veya.domain.models import DomainError
from veya.finance.models import Money
from veya.ingestion.intake import validate
from veya.ingestion.worker import extract


def test_money_is_exact_and_rejects_cross_currency_and_negative():
    money = Money(amount='12.30', currency='USD')
    assert money.add(Money(amount='0.20', currency='USD')).amount == '12.50'
    with pytest.raises(ValueError):
        Money(amount='-1', currency='USD')
    with pytest.raises(DomainError):
        money.add(Money(amount='1.00', currency='EUR'))


def test_email_body_and_attachment_keep_shared_source_provenance():
    message = EmailMessage()
    message['From'] = 'fixture@example.invalid'
    message['Date'] = 'Sun, 25 Oct 2026 12:00:00 +0000'
    message['Subject'] = 'Fixture purchase order'
    message.set_content('Please inspect the attached order.')
    message.add_attachment(b'amount\n12.30\n', maintype='text', subtype='csv', filename='Order.csv')
    raw = message.as_bytes()
    assert validate('Order.eml', raw) == 'eml'
    result = extract('eml', raw)
    assert any(
        b['locator'] == 'email:from' and 'fixture@example.invalid' in b['text']
        for b in result['blocks']
    )
    assert any(
        b['locator'] == 'attachment:Order.csv/CSV!A2' and b['text'] == '12.30'
        for b in result['blocks']
    )


def invoice(vendor='Fixture supplier', number='INV-001'):
    from veya.finance.models import Invoice, Line

    return Invoice(
        vendor=vendor,
        number=number,
        issued='2026-10-25',
        lines=(
            Line(
                item='part',
                quantity='2',
                unit_price=Money(amount='12.30', currency='USD'),
                tax=Money(amount='1.00', currency='USD'),
            ),
        ),
        total=Money(amount='25.60', currency='USD'),
    )


def test_invoice_duplicates_preserve_vendor_identity_and_changed_content(tmp_path):
    from veya.finance.duplicates import register
    from veya.storage.sqlite import Database

    db = Database(tmp_path)
    first = register(db, 't', invoice())
    assert not first['reused']
    assert register(db, 't', invoice(vendor=' FIXTURE supplier '))['reused']
    other = register(db, 't', invoice(vendor='Another supplier'))
    assert other['candidate_id'] != first['candidate_id'] and not other['possible_duplicates']
    similar = register(db, 't', invoice(number='INV-002'))
    assert similar['possible_duplicates'] == [first['candidate_id']]
    with pytest.raises(DomainError):
        register(db, 't', invoice().model_copy(update={'issued': '2026-10-24'}))
    assert not register(db, 'other', invoice())['reused']


def test_policy_history_overlap_and_revocation_require_review(tmp_path):
    from datetime import date

    from veya.finance.policy import Policy, resolve
    from veya.ingestion.jobs import Documents
    from veya.storage.sqlite import Database

    db = Database(tmp_path)
    docs = Documents(db, 't')
    first = docs.intake('a', 'Policy.csv', b'limit\n100.00\n')
    docs.process(first['id'])
    second = docs.intake('b', 'Policy.csv', b'limit\n10.00\n')
    docs.process(second['id'])
    old = Policy(
        'old',
        date(2026, 1, 1),
        date(2027, 1, 1),
        Money(amount='100.00', currency='USD'),
        first['id'] + ':0',
    )
    new = Policy(
        'new',
        date(2027, 1, 1),
        date(2028, 1, 1),
        Money(amount='10.00', currency='USD'),
        second['id'] + ':0',
    )
    result = resolve(db, 't', invoice(), [old, new])
    assert (
        result['policy_id'] == 'old'
        and not result['review_required']
        and result['source']['version'] == 1
    )
    assert resolve(db, 't', invoice(), [old, old])['reason'] == 'overlapping_policy'
    assert resolve(db, 't', invoice(), [])['reason'] == 'missing_policy'
    docs.revoke(first['id'])
    assert resolve(db, 't', invoice(), [old, new])['reason'] == 'policy_evidence_unavailable'


def test_chunking_is_bounded_and_reconstructs_exact_offsets():
    from veya.retrieval.chunking import chunks

    text = 'ab cd ' * 1000
    result = chunks(
        {
            'version': 2,
            'blocks': [
                {'text': text, 'citation': 'doc_1:0', 'locator': 'page:2:block:3'},
                {'text': '', 'citation': 'doc_1:1', 'locator': 'empty'},
            ],
        },
        128,
    )
    assert ''.join(r['text'] for r in result) == text
    assert all(
        text[r['start'] : r['end']] == r['text']
        and r['version'] == 2
        and r['citation'] == 'doc_1:0'
        for r in result
    )
    with pytest.raises(DomainError):
        chunks({'blocks': []}, 0)


def test_email_rejects_nested_unsafe_and_oversize_attachments():
    from email.message import EmailMessage

    for name, content in [
        ('nested.eml', b'From: a@example.invalid\n\nbody'),
        ('../secret.csv', b'a\n1'),
        ('bad.exe', b'MZxxx'),
        ('huge.csv', b'a' * 524289),
    ]:
        message = EmailMessage()
        message['From'] = 'fixture@example.invalid'
        message['Date'] = 'Sun, 25 Oct 2026 12:00:00 +0000'
        message.set_content('Fixture')
        message.add_attachment(
            content, maintype='application', subtype='octet-stream', filename=name
        )
        with pytest.raises(DomainError):
            validate('Unsafe.eml', message.as_bytes())


@pytest.mark.parametrize('payload', [b'SGVsbG8===!', b'a'])
def test_malformed_email_base64_is_rejected(payload):
    raw = (
        b'From: fixture@example.invalid\nDate: Sun, 25 Oct 2026 12:00:00 +0000\n'
        b'Content-Type: text/plain\nContent-Transfer-Encoding: base64\n\n' + payload
    )
    with pytest.raises(DomainError):
        validate('bad.eml', raw)
