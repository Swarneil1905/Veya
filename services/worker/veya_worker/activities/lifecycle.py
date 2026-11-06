"""Activities preserve effect identity and heartbeat only durable progress."""

from temporalio import activity
from temporalio.exceptions import ApplicationError

from veya_worker.contracts import Operation


class Activities:
    def __init__(self, store, *, faults=None):
        self.store = store
        self.faults = faults or {}

    @activity.defn(name='veya.perform.v1')
    async def perform(self, request: dict) -> dict:
        op = Operation(**request['operation'])
        activity.heartbeat({'id': op.id, 'state': 'before_effect'})
        if activity.is_cancelled():
            return {'id': op.id, 'state': 'cancelled'}
        try:
            result = self.store.perform(op, request['receipt'], fault=self.faults.get(op.id))
        except PermissionError as error:
            raise ApplicationError(str(error), non_retryable=True) from error
        activity.heartbeat(result)
        return result

    @activity.defn(name='veya.reconcile.v1')
    async def reconcile(self, request: dict) -> dict:
        result = self.store.reconcile(Operation(**request))
        activity.heartbeat(result)
        return result

    @activity.defn(name='veya.compensate.v1')
    async def compensate(self, request: dict) -> dict:
        result = self.store.compensate(Operation(**request))
        activity.heartbeat(result)
        return result

    def registered(self):
        return [self.perform, self.reconcile, self.compensate]
