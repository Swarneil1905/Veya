"""Per-call usage evidence. Estimates never replace provider-reported usage.

Host adapters call begin before dispatch and finish after a response. Unfinished,
failed, unpriced or missing-usage calls keep the run total explicitly incomplete.
No provider adapter or live inference is introduced by this storage contract.
"""

import hashlib
import json

from veya.domain.models import DomainError, identifier, utc_now
from veya.events.store import append_event
from veya.providers.models import ModelConfig
from veya.storage.sqlite import Database
from veya.tools.contracts import canonical_json


def tokens(value):
    if value is not None and (type(value) is not int or not 0 <= value <= 10**12):
        raise DomainError(
            'invalid_input', 'Token usage must be a nonnegative bounded integer or unknown'
        )
    return value


def numerator(price, input_tokens, output_tokens):
    if price is None or input_tokens is None or output_tokens is None:
        return None
    incoming, outgoing = (
        price['input_microunits_per_million_tokens'],
        price['output_microunits_per_million_tokens'],
    )
    if incoming is None or outgoing is None:
        return None
    return input_tokens * incoming + output_tokens * outgoing


def money(value: int) -> str:
    # Exact fixed-point units; no binary floats and no per-call rounding drift.
    whole, fraction = divmod(value, 10**12)
    return f'{whole}.{fraction:012d}'.rstrip('0').rstrip('.')


class UsageStore:
    def __init__(self, db: Database):
        self.db = db

    def begin(
        self,
        tenant: str,
        run_id: str,
        call_id: str,
        model: ModelConfig,
        *,
        estimated_input=None,
        estimated_output=None,
    ):
        for value in (tenant, run_id, call_id):
            identifier(value)
        price = model.price.model_dump(mode='json') if model.price else None
        if price and any(
            v is not None and v > 10**18 for k, v in price.items() if k.endswith('_tokens')
        ):
            raise DomainError('invalid_input', 'Price exceeds supported accounting precision')
        request = {
            'model_config_id': model.id,
            'provider_id': model.provider_id,
            'model_name': model.model_name,
            'config_hash': model.fingerprint,
            'price': price,
            'price_version': hashlib.sha256(canonical_json(price, 4096).encode()).hexdigest()
            if price
            else None,
            'estimated_input': tokens(estimated_input),
            'estimated_output': tokens(estimated_output),
        }
        payload = canonical_json(request, 16_384)
        with self.db.transaction() as conn:
            row = conn.execute(
                'SELECT run_id,request_json FROM provider_usage WHERE tenant_id=? AND call_id=?',
                (tenant, call_id),
            ).fetchone()
            if row:
                if row['run_id'] != run_id or row['request_json'] != payload:
                    raise DomainError(
                        'conflict',
                        'Call identity is already bound to different accounting evidence',
                    )
                return
            run = conn.execute(
                'SELECT state FROM runs WHERE tenant_id=? AND id=?', (tenant, run_id)
            ).fetchone()
            if run is None:
                raise DomainError('not_found', 'Run not found')
            if run['state'] in {'failed', 'cancelled', 'succeeded'}:
                raise DomainError('conflict', 'Run is terminal')
            conn.execute(
                'INSERT INTO provider_usage (tenant_id,run_id,call_id,request_json,created_at) VALUES (?,?,?,?,?)',
                (tenant, run_id, call_id, payload, utc_now()),
            )
            append_event(
                conn,
                tenant,
                run_id,
                'model.usage_pending',
                {'call_id': call_id, 'config_hash': model.fingerprint},
            )

    def finish(
        self, tenant: str, call_id: str, *, status: str, reported_input=None, reported_output=None
    ):
        if status not in {'completed', 'failed'}:
            raise DomainError('invalid_input', 'Invalid call outcome')
        payload = canonical_json(
            {
                'status': status,
                'reported_input': tokens(reported_input),
                'reported_output': tokens(reported_output),
                'source': 'provider_reported',
            },
            4096,
        )
        with self.db.transaction() as conn:
            row = conn.execute(
                'SELECT run_id,report_json FROM provider_usage WHERE tenant_id=? AND call_id=?',
                (tenant, call_id),
            ).fetchone()
            if row is None:
                raise DomainError('not_found', 'Call not found')
            if row['report_json'] is not None:
                if row['report_json'] != payload:
                    raise DomainError('conflict', 'Call usage is already finalized')
                return
            conn.execute(
                'UPDATE provider_usage SET report_json=? WHERE tenant_id=? AND call_id=?',
                (payload, tenant, call_id),
            )
            append_event(
                conn,
                tenant,
                row['run_id'],
                'model.usage_recorded',
                {
                    'call_id': call_id,
                    'status': status,
                    'usage_known': reported_input is not None and reported_output is not None,
                },
            )

    def _run(self, conn, tenant, run_id):
        if (
            conn.execute(
                'SELECT 1 FROM runs WHERE tenant_id=? AND id=?', (tenant, run_id)
            ).fetchone()
            is None
        ):
            raise DomainError('not_found', 'Run not found')

    def page(self, tenant: str, run_id: str, *, after: int = 0, limit: int = 50) -> dict:
        if (
            type(after) is not int
            or not 0 <= after <= 2**63 - 1
            or type(limit) is not int
            or not 1 <= limit <= 100
        ):
            raise DomainError('invalid_input', 'Invalid usage page')
        with self.db.connection() as conn:
            self._run(conn, tenant, run_id)
            rows = conn.execute(
                'SELECT * FROM provider_usage WHERE tenant_id=? AND run_id=? AND sequence>? ORDER BY sequence LIMIT ?',
                (tenant, run_id, after, limit + 1),
            ).fetchall()
        items = []
        for row in rows[:limit]:
            request = json.loads(row['request_json'])
            report = json.loads(row['report_json']) if row['report_json'] else None
            value = (
                numerator(request['price'], report['reported_input'], report['reported_output'])
                if report
                else None
            )
            items.append(
                {
                    'call_id': row['call_id'],
                    **request,
                    'report': report,
                    'reported_cost': money(value) if value is not None else None,
                }
            )
        return {
            'items': items,
            'next_cursor': rows[limit - 1]['sequence'] if len(rows) > limit else None,
        }

    def summary(self, tenant: str, run_id: str) -> dict:
        count = unknown = 0
        reported: dict[str, int] = {}
        estimated: dict[str, int] = {}
        with self.db.connection() as conn:
            conn.execute('BEGIN')
            self._run(conn, tenant, run_id)
            for row in conn.execute(
                'SELECT request_json,report_json FROM provider_usage WHERE tenant_id=? AND run_id=?',
                (tenant, run_id),
            ):
                count += 1
                request = json.loads(row['request_json'])
                report = json.loads(row['report_json']) if row['report_json'] else None
                price = request['price']
                actual = (
                    numerator(price, report['reported_input'], report['reported_output'])
                    if report
                    else None
                )
                estimate = numerator(price, request['estimated_input'], request['estimated_output'])
                if actual is None or report is None or report['status'] != 'completed':
                    unknown += 1
                if actual is not None:
                    reported[price['currency']] = reported.get(price['currency'], 0) + actual
                if estimate is not None:
                    estimated[price['currency']] = estimated.get(price['currency'], 0) + estimate
        return {
            'calls': count,
            'unknown_calls': unknown,
            'complete': unknown == 0,
            'reported_costs': {k: money(v) for k, v in reported.items()},
            'estimated_costs': {k: money(v) for k, v in estimated.items()},
        }
