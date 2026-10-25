"""Conservative upper-bound reservations, committed before model/tool effects.

Reservations never refund automatically, including cancellation and unknown
outcomes. This is admission control, not measured provider billing. Callers must
enforce the declared token/output bounds in their adapters.
"""
import asyncio
from dataclasses import asdict, dataclass
import json
import math
import re
import time
from typing import Awaitable, Callable

from veya.domain.models import DomainError, identifier
from veya.events.store import append_event
from veya.providers.models import PriceMetadata
from veya.storage.sqlite import Database
from veya.tools.contracts import canonical_json
from veya.tools.retries import _bounded


def nonnegative(value):
    if type(value) is not int or not 0 <= value <= 2**53 - 1:
        raise ValueError('Counts must be nonnegative safe integers')


def currency(value):
    if value is not None and (type(value) is not str or not re.fullmatch('[A-Z]{3}', value)):
        raise ValueError('Currency must be explicit or unknown')


@dataclass(frozen=True)
class BudgetLimits:
    tokens: int
    tool_steps: int
    wall_seconds: float
    max_cost_microunits: int | None
    currency: str | None
    allow_unpriced: bool

    def __post_init__(self):
        nonnegative(self.tokens)
        nonnegative(self.tool_steps)
        currency(self.currency)
        if type(self.wall_seconds) not in {int, float} or not math.isfinite(self.wall_seconds) or self.wall_seconds <= 0:
            raise ValueError('An explicit positive wall-time budget is required')
        if type(self.allow_unpriced) is not bool:
            raise ValueError('Explicit unknown-price policy is required')
        if self.max_cost_microunits is not None:
            nonnegative(self.max_cost_microunits)
            if self.currency is None:
                raise ValueError('Monetary budgets require a currency')


@dataclass(frozen=True)
class ActionEstimate:
    tokens: int
    tool_steps: int
    cost_microunits: int | None
    currency: str | None

    def __post_init__(self):
        nonnegative(self.tokens)
        nonnegative(self.tool_steps)
        currency(self.currency)
        if self.cost_microunits is not None:
            nonnegative(self.cost_microunits)
            if self.cost_microunits and self.currency is None:
                raise ValueError('Priced actions require a currency')

    @classmethod
    def inference(cls, input_tokens: int, output_tokens: int, price: PriceMetadata | None):
        nonnegative(input_tokens)
        nonnegative(output_tokens)
        cost = None
        if price is not None and price.input_microunits_per_million_tokens is not None and price.output_microunits_per_million_tokens is not None:
            numerator = input_tokens * price.input_microunits_per_million_tokens + output_tokens * price.output_microunits_per_million_tokens
            cost = (numerator + 999_999) // 1_000_000
        return cls(input_tokens + output_tokens, 0, cost, price.currency if price else None)


@dataclass(frozen=True)
class Reservation:
    created: bool
    started_at: float
    deadline: float


class BudgetStore:
    def __init__(self, db: Database, *, clock: Callable[[], float] = time.time):
        self.db, self.clock = db, clock

    def remaining(self, reservation: Reservation) -> float:
        now = self.clock()
        if type(now) not in {int, float} or not math.isfinite(now) or not reservation.started_at <= now < reservation.deadline:
            raise DomainError('budget_exceeded', 'Run time budget is unavailable or exhausted')
        return reservation.deadline - now

    def configure(self, tenant: str, run_id: str, limits: BudgetLimits):
        identifier(tenant)
        identifier(run_id)
        if type(limits) is not BudgetLimits:
            raise ValueError('Typed budget limits required')
        encoded = canonical_json(asdict(limits), 4096)
        now = self.clock()
        if type(now) not in {int, float} or not math.isfinite(now) or not math.isfinite(now + limits.wall_seconds):
            raise ValueError('A finite clock and deadline are required')
        with self.db.transaction() as conn:
            row = conn.execute('SELECT limits_json FROM run_budgets WHERE tenant_id=? AND run_id=?', (tenant, run_id)).fetchone()
            if row:
                if row[0] != encoded:
                    raise DomainError('conflict', 'Run budget already configured differently')
                return
            self._run(conn, tenant, run_id)
            conn.execute('INSERT INTO run_budgets VALUES (?,?,?,?,?)', (tenant, run_id, encoded, now, now + limits.wall_seconds))

    @staticmethod
    def _run(conn, tenant, run_id):
        row = conn.execute('SELECT state FROM runs WHERE tenant_id=? AND id=?', (tenant, run_id)).fetchone()
        if row is None or row[0] in {'succeeded', 'failed', 'cancelled'}:
            raise DomainError('conflict', 'Run cannot admit budgeted work')

    @staticmethod
    def _usage(conn, tenant, run_id):
        row = conn.execute('SELECT COALESCE(sum(tokens),0),COALESCE(sum(tool_steps),0),COALESCE(sum(cost),0),'
                           'count(*)-count(cost) FROM budget_reservations WHERE tenant_id=? AND run_id=?', (tenant, run_id)).fetchone()
        return {'tokens': row[0], 'tool_steps': row[1], 'known_cost_microunits': row[2],
                'unpriced_actions': row[3], 'estimated_cost_microunits': None if row[3] else row[2]}

    def usage(self, tenant: str, run_id: str) -> dict:
        with self.db.connection() as conn:
            if conn.execute('SELECT 1 FROM run_budgets WHERE tenant_id=? AND run_id=?', (tenant, run_id)).fetchone() is None:
                raise DomainError('not_found', 'Run budget not found')
            return self._usage(conn, tenant, run_id)

    def reserve_in_transaction(self, conn, tenant: str, run_id: str, action_id: str, estimate: ActionEstimate) -> Reservation:
        if not conn.in_transaction or type(estimate) is not ActionEstimate:
            raise ValueError('Typed estimate and write transaction required')
        for value in (tenant, run_id, action_id):
            identifier(value)
        encoded = canonical_json(asdict(estimate), 4096)
        self._run(conn, tenant, run_id)
        row = conn.execute('SELECT * FROM run_budgets WHERE tenant_id=? AND run_id=?', (tenant, run_id)).fetchone()
        if row is None:
            raise DomainError('budget_required', 'Configure a run budget before dispatch')
        reservation = Reservation(True, row['started_at'], row['deadline'])
        self.remaining(reservation)
        existing = conn.execute('SELECT estimate_json FROM budget_reservations WHERE tenant_id=? AND run_id=? AND action_id=?',
                                (tenant, run_id, action_id)).fetchone()
        if existing:
            if existing[0] != encoded:
                raise DomainError('conflict', 'Budget key names a different action estimate')
            return Reservation(False, reservation.started_at, reservation.deadline)
        limits = BudgetLimits(**json.loads(row['limits_json']))
        used = self._usage(conn, tenant, run_id)
        if estimate.cost_microunits is None and not limits.allow_unpriced:
            raise DomainError('budget_unpriced', 'Unknown price is not permitted by this run budget')
        if estimate.cost_microunits and estimate.currency != limits.currency:
            raise DomainError('budget_currency', 'Action currency does not match the run budget')
        if (used['known_cost_microunits'] + (estimate.cost_microunits or 0) > 2**53 - 1 or
            used['tokens'] + estimate.tokens > limits.tokens or used['tool_steps'] + estimate.tool_steps > limits.tool_steps or
            (limits.max_cost_microunits is not None and used['known_cost_microunits'] + (estimate.cost_microunits or 0) > limits.max_cost_microunits)):
            raise DomainError('budget_exceeded', 'Next action exceeds the configured run budget')
        conn.execute('INSERT INTO budget_reservations VALUES (?,?,?,?,?,?,?)',
                     (tenant, run_id, action_id, encoded, estimate.tokens, estimate.tool_steps, estimate.cost_microunits))
        append_event(conn, tenant, run_id, 'budget.reserved', {'action_id': action_id, **asdict(estimate)})
        return reservation

    def reserve(self, tenant: str, run_id: str, action_id: str, estimate: ActionEstimate) -> Reservation:
        with self.db.transaction() as conn:
            return self.reserve_in_transaction(conn, tenant, run_id, action_id, estimate)

    async def execute(self, tenant: str, run_id: str, action_id: str, estimate: ActionEstimate,
                      operation: Callable[[], Awaitable[dict]]) -> dict:
        reservation = await asyncio.to_thread(self.reserve, tenant, run_id, action_id, estimate)
        if not reservation.created:
            raise DomainError('conflict', 'Budgeted action was already admitted; reconcile its outcome')
        return await _bounded(operation, self.remaining(reservation))
