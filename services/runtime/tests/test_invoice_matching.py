import pytest

from veya.finance.matching import Tolerance, match
from veya.finance.models import Invoice, Line, Money, Order, Receipt


def records(billed='120', received='100', price='12'):
    line = Line(
        item='part',
        quantity=billed,
        unit_price=Money(amount=price, currency='USD'),
        tax=Money(amount='0', currency='USD'),
    )
    inv = Invoice(
        vendor='Fixture supplier',
        number='INV-1',
        issued='2026-10-25',
        lines=(line,),
        total=line.total(),
    )
    order = Order(
        vendor=inv.vendor, number='PO-1', lines=(line.model_copy(update={'quantity': '120'}),)
    )
    receipts = (
        Receipt(
            vendor=inv.vendor, order_number='PO-1', item='part', quantity=received, state='received'
        ),
    )
    return inv, order, receipts


def test_three_way_matching_keeps_exact_discrepancy_and_missing_receipt():
    inv, order, receipts = records()
    result = match(inv, order, receipts)
    assert result.status == 'mismatch'
    assert result.discrepancy == '240' and result.currency == 'USD'
    assert result.lines[0].accepted_quantity == '100'
    missing = match(inv, order, ())
    assert missing.status == 'review_required' and missing.discrepancy is None


def test_tolerance_is_inclusive_without_rounding_partial_deliveries_away():
    inv, order, receipts = records(billed='100.001', received='100', price='12')
    assert match(inv, order, receipts).discrepancy == '0.012'
    assert (
        match(inv, order, receipts, Tolerance(quantity='0.001', amount='0.012')).status == 'matched'
    )
    assert (
        match(inv, order, receipts, Tolerance(quantity='0.001', amount='0.011')).status
        == 'mismatch'
    )


def test_partial_delivery_returns_and_duplicate_receipts_require_exact_evidence():
    inv, order, receipts = records()
    returned = receipts[0].model_copy(update={'quantity': '10', 'state': 'returned'})
    assert match(inv, order, receipts + (returned,)).discrepancy == '360'
    assert match(inv, order, receipts + receipts).reasons == ('ambiguous_duplicate_receipts',)
    assert match(inv, order, (returned,)).status == 'review_required'
    assert (
        match(inv, order, (receipts[0].model_copy(update={'order_number': 'other'}),)).status
        == 'review_required'
    )


def test_offsetting_line_mismatches_do_not_cancel_each_other():
    inv, order, receipts = records(billed='100', received='100')
    expensive = inv.lines[0].model_copy(
        update={'item': 'expensive', 'unit_price': Money(amount='13', currency='USD')}
    )
    cheaper = inv.lines[0].model_copy(
        update={'item': 'cheaper', 'unit_price': Money(amount='11', currency='USD')}
    )
    inv = inv.model_copy(
        update={'lines': (expensive, cheaper), 'total': Money(amount='2400', currency='USD')}
    )
    order = order.model_copy(
        update={
            'lines': tuple(
                order.lines[0].model_copy(update={'item': item})
                for item in ['expensive', 'cheaper']
            )
        }
    )
    receipts = tuple(
        receipts[0].model_copy(update={'item': item}) for item in ['expensive', 'cheaper']
    )
    result = match(inv, order, receipts)
    assert result.discrepancy == '0' and result.status == 'mismatch'


def test_fractional_tax_requires_rounding_policy_and_currency_never_converts():
    inv, order, receipts = records(billed='1', received='1')
    order = order.model_copy(
        update={
            'lines': (
                order.lines[0].model_copy(
                    update={'quantity': '3', 'tax': Money(amount='1', currency='USD')}
                ),
            )
        }
    )
    assert match(inv, order, receipts).reasons == ('tax_allocation_requires_rounding_policy',)
    order = order.model_copy(
        update={
            'lines': (
                order.lines[0].model_copy(
                    update={
                        'unit_price': Money(amount='12', currency='EUR'),
                        'tax': Money(amount='0', currency='EUR'),
                    }
                ),
            )
        }
    )
    assert match(inv, order, receipts).reasons == ('currency_mismatch',)
    with pytest.raises(ValueError):
        match(inv, order, receipts, Tolerance().model_copy(update={'amount': 'NaN'}))
