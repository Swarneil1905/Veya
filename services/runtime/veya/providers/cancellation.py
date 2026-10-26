"""Poll durable cancellation while an owned asynchronous request is in flight."""

import asyncio

from veya.domain.models import DomainError


async def while_running(db, tenant, run_id, operation):
    task = asyncio.create_task(operation)
    try:
        while True:
            if db.get_run(tenant, run_id).state != 'running':
                raise DomainError('cancelled', 'Run is no longer executable')
            done, _ = await asyncio.wait({task}, timeout=0.1)
            if done:
                result = task.result()
                if db.get_run(tenant, run_id).state != 'running':
                    raise DomainError('cancelled', 'Late response discarded')
                return result
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
