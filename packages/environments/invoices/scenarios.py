"""Small synthetic cases; expected outcomes stay in the host's evaluation configuration."""

import hashlib
from decimal import Decimal

from veya.finance.models import Invoice, Line, Money, Order, Receipt

from packages.environments.snapshot import FixturePolicy, FixtureUser, Snapshot, Source


def shortage(*, billed='120', received='100', price='12', case_id='fixture_shortage'):
    unit = Money(amount=price, currency='USD')
    tax = Money(amount='0', currency='USD')
    line = Line(item='Fixture part', quantity=billed, unit_price=unit, tax=tax)
    invoice = Invoice(
        vendor='Fixture supplier',
        number='INV-1',
        issued='2026-10-25',
        lines=(line,),
        total=Money(amount=format(Decimal(billed) * Decimal(price), 'f'), currency='USD'),
    )
    order = Order(vendor=invoice.vendor, number='PO-1', lines=(line,))
    receipt = Receipt(
        vendor=invoice.vendor,
        order_number=order.number,
        item=line.item,
        quantity=received,
        state='received',
    )
    content = f'billed,received,unit_price\n{billed},{received},{price}\n'.encode()
    digest = hashlib.sha256(content).hexdigest()
    snapshot = Snapshot(
        case_id=case_id,
        version='v1',
        family='quantity_shortage',
        lineage='synthetic_supplier_1',
        tenant='fixture_evaluation',
        invoice=invoice,
        order=order,
        receipts=(receipt,),
        sources=(
            Source(id='invoice_source', name='Invoice.csv', digest=digest, size=len(content)),
        ),
        users=(FixtureUser(id='reviewer', role='reviewer'),),
        policy=FixturePolicy(version='policy_1'),
    )
    return snapshot, {digest: content}
