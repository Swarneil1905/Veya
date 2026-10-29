"""Currency-separated reconciliation. Pending, unknown and negative differences stay visible."""

import json
from decimal import Decimal, localcontext

from veya.finance.agent import InvoicePacket


def result_pack(agent, run_ids):
    if not 1 <= len(run_ids) <= 100 or len(set(run_ids)) != len(run_ids):
        raise ValueError('Choose 1 to 100 distinct invoice runs')
    items = []
    totals: dict[str, dict] = {}
    with localcontext() as context:
        context.prec = 80
        for run_id in run_ids:
            row = agent.get(run_id)
            packet = InvoicePacket.model_validate_json(row['packet_json'])
            assessment = json.loads(row['assessment_json'])
            outcome = json.loads(row['outcome_json']) if row['outcome_json'] else None
            discrepancy = assessment['match']['discrepancy']
            currency = packet.invoice.total.currency
            total = totals.setdefault(
                currency, {'invoiced': Decimal(0), 'known_discrepancy': Decimal(0), 'unknown': 0}
            )
            total['invoiced'] += Decimal(packet.invoice.total.amount)
            if discrepancy is None:
                total['unknown'] += 1
            else:
                total['known_discrepancy'] += Decimal(discrepancy)
            items.append(
                {
                    'run_id': run_id,
                    'invoice': packet.invoice.number,
                    'discrepancy': discrepancy,
                    'currency': currency,
                    'state': outcome['state'] if outcome else assessment['state'],
                    'draft_id': outcome['draft_id'] if outcome else None,
                    'evidence': assessment['evidence'],
                    'reason': outcome['reason'] if outcome else assessment['reason'],
                }
            )
    return {
        'complete': all(i['state'] == 'succeeded' for i in items),
        'fixture': True,
        'items': items,
        'totals': {
            currency: {k: format(v, 'f') if isinstance(v, Decimal) else v for k, v in total.items()}
            for currency, total in totals.items()
        },
    }
