"""Three-way checks over reviewed records. No implicit FX, rounding or tax policy."""

from decimal import Decimal, Inexact, localcontext
from typing import Literal

from pydantic import field_validator

from veya.finance.models import Invoice, Order, Receipt, Value, decimal


class Tolerance(Value):
    quantity: str = '0'
    amount: str = '0'

    @field_validator('quantity', 'amount')
    @classmethod
    def bounded(cls, value):
        decimal(value)
        return value


class LineMatch(Value):
    item: str
    accepted_quantity: str
    quantity_difference: str
    discrepancy: str
    matched: bool


class Match(Value):
    status: Literal['matched', 'mismatch', 'review_required']
    currency: str
    discrepancy: str | None
    lines: tuple[LineMatch, ...] = ()
    reasons: tuple[str, ...] = ()


def match(
    invoice: Invoice,
    order: Order,
    receipts: tuple[Receipt, ...],
    tolerance: Tolerance | None = None,
) -> Match:
    # Revalidate even trusted callers' model_copy updates at this boundary.
    invoice = Invoice.model_validate_json(invoice.model_dump_json())
    order = Order.model_validate_json(order.model_dump_json())
    receipts = tuple(Receipt.model_validate_json(r.model_dump_json()) for r in receipts)
    tolerance = tolerance or Tolerance()
    tolerance = Tolerance.model_validate_json(tolerance.model_dump_json())
    if len(receipts) > 1000:
        raise ValueError('At most 1000 receipt records per comparison')
    currency = invoice.total.currency

    def review(reason):
        return Match(
            status='review_required', currency=currency, discrepancy=None, reasons=(reason,)
        )

    if invoice.vendor != order.vendor:
        return review('vendor_mismatch')
    ordered = {line.item: line for line in order.lines}
    if len(ordered) != len(order.lines) or len({line.item for line in invoice.lines}) != len(
        invoice.lines
    ):
        return review('ambiguous_line_identity')
    if any(line.unit_price.currency != currency for line in order.lines):
        return review('currency_mismatch')
    if not receipts:
        return review('missing_receipt')
    if len({r.model_dump_json() for r in receipts}) != len(receipts):
        return review('ambiguous_duplicate_receipts')
    if any(
        r.vendor != invoice.vendor or r.order_number != order.number or r.item not in ordered
        for r in receipts
    ):
        return review('receipt_identity_mismatch')
    results = []
    with localcontext() as context:
        context.prec = 80
        context.traps[Inexact] = True
        received: dict[str, Decimal] = {}
        for r in receipts:
            received[r.item] = received.get(r.item, Decimal(0)) + decimal(r.quantity) * (
                1 if r.state == 'received' else -1
            )
        for line in invoice.lines:
            if line.item not in ordered or line.item not in received:
                return review('missing_order_or_receipt_line')
            item = ordered[line.item]
            if received[line.item] < 0:
                return review('returns_exceed_receipts')
            billed, quantity = decimal(line.quantity), decimal(item.quantity)
            accepted = min(billed, quantity, received[line.item])
            try:
                expected_tax = decimal(item.tax.amount) * accepted / quantity
            except Inexact:
                return review('tax_allocation_requires_rounding_policy')
            delta = (
                billed * decimal(line.unit_price.amount)
                + decimal(line.tax.amount)
                - accepted * decimal(item.unit_price.amount)
                - expected_tax
            )
            shortage = billed - accepted
            results.append(
                LineMatch(
                    item=line.item,
                    accepted_quantity=format(accepted, 'f'),
                    quantity_difference=format(shortage, 'f'),
                    discrepancy=format(delta, 'f'),
                    matched=shortage <= decimal(tolerance.quantity)
                    and abs(delta) <= decimal(tolerance.amount),
                )
            )
        total = sum((Decimal(line.discrepancy) for line in results), Decimal(0))
    return Match(
        status='matched' if all(line.matched for line in results) else 'mismatch',
        currency=currency,
        discrepancy=format(total, 'f'),
        lines=tuple(results),
    )
