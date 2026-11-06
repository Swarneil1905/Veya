"""V1 orchestration: review, effect, reconciliation, bounded compensation."""

import asyncio
from dataclasses import asdict
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError, CancelledError

from veya_worker.contracts import TaskInput


@workflow.defn(name='VeyaTaskV1')
class TaskWorkflow:
    def __init__(self):
        self.receipts = {}
        self.current = None
        self.cancel_requested = False
        self.state = 'starting'
        self.completed = []

    @workflow.signal
    def review(self, value: dict):
        # Signals wake the workflow; the activity validates actual authority.
        if (
            self.current
            and value.get('operation_id') == self.current.id
            and value.get('digest') == self.current.digest
            and value.get('tenant') == self.current.tenant
            and isinstance(value.get('receipt'), str)
            and 1 <= len(value['receipt']) <= 100
        ):
            self.receipts.setdefault(self.current.id, value['receipt'])

    @workflow.signal
    def request_cancel(self):
        self.cancel_requested = True

    @workflow.query
    def status(self) -> dict:
        return {
            'state': self.state,
            'operation_id': self.current.id if self.current else None,
            'completed': list(self.completed),
        }

    async def activity(self, name, request):
        return await workflow.execute_activity(
            name,
            request,
            start_to_close_timeout=timedelta(seconds=30),
            heartbeat_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
            cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
        )

    async def unwind(self, operations):
        outcomes = []
        for op in reversed(operations):
            try:
                result = await self.activity('veya.compensate.v1', asdict(op))
            except ActivityError:
                result = {'id': op.id, 'state': 'residual'}
            outcomes.append(result)
        return outcomes

    @workflow.run
    async def run(self, task: TaskInput) -> dict:
        try:
            return await self.execute(task)
        except asyncio.CancelledError:
            # Cancellation cannot establish whether an in-flight effect committed.
            async def recover():
                outcomes = []
                if self.current and self.state in {'executing', 'reconciling'}:
                    try:
                        outcomes.append(
                            await self.activity('veya.reconcile.v1', asdict(self.current))
                        )
                    except ActivityError:
                        outcomes.append({'id': self.current.id, 'state': 'unknown'})
                self.state = 'cancelled' if not outcomes else 'review_required'
                return {
                    'state': self.state,
                    'operations': self.completed + outcomes,
                    'compensation': [],
                    'requires_review': bool(outcomes or self.completed),
                }

            return await asyncio.shield(recover())

    async def execute(self, task: TaskInput) -> dict:
        try:
            task.validate()
        except ValueError as error:
            raise ApplicationError(str(error), non_retryable=True) from error
        applied = []
        failure = None
        for op in task.operations:
            self.current = op
            self.state = 'awaiting_review'
            try:
                await workflow.wait_condition(
                    lambda op=op: op.id in self.receipts or self.cancel_requested,
                    timeout=timedelta(seconds=task.review_seconds),
                )
            except TimeoutError:
                failure = 'review_expired'
                break
            if self.cancel_requested:
                failure = 'cancelled'
                break
            self.state = 'executing'
            try:
                result = await self.activity(
                    'veya.perform.v1',
                    {'operation': asdict(op), 'receipt': self.receipts.pop(op.id)},
                )
            except ActivityError as error:
                if isinstance(error.cause, CancelledError):
                    raise asyncio.CancelledError() from error
                self.state = 'reconciling'
                try:
                    result = await self.activity('veya.reconcile.v1', asdict(op))
                except ActivityError:
                    result = {'state': 'unknown', 'id': op.id}
            self.completed.append(result)
            if result['state'] != 'applied':
                failure = result['state']
                break
            applied.append(op)
        residuals = await self.unwind(applied) if failure else []
        self.state = failure or 'succeeded'
        return {
            'state': self.state,
            'operations': self.completed,
            'compensation': residuals,
            'requires_review': self.state == 'unknown'
            or any(item['state'] == 'residual' for item in residuals),
        }
