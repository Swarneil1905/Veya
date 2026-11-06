"""Host-selected verification adds evidence, never tool permissions."""

import asyncio
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationPolicy:
    version: str
    required_reasons: frozenset[str]

    def select(self, task_id, reasons):
        if not self.version or not task_id:
            raise ValueError('Task and policy version are required')
        return sorted(set(reasons) & self.required_reasons)

    async def evaluate(
        self,
        task_id,
        reasons,
        verify,
        *,
        clock=time.monotonic,
        timeout_seconds=30,
    ):
        if not 0 < timeout_seconds <= 120:
            raise ValueError('Verifier requires a bounded deadline')
        selected = self.select(task_id, reasons)
        started = clock()
        verdict = 'not_required'
        error = None
        if selected:
            try:
                answer = await asyncio.wait_for(verify(), timeout_seconds)
                if type(answer) is not bool:
                    raise ValueError('Verifier must return an explicit decision')
                verdict = 'passed' if answer else 'failed'
            except Exception as failure:
                verdict = 'failed'
                error = type(failure).__name__
        return {
            'task_id': task_id,
            'policy_version': self.version,
            'reasons': selected,
            'verdict': verdict,
            'added_latency_ms': max(0, round((clock() - started) * 1000)),
            'error': error,
            'grants': [],
        }


def record(connection, tenant, run_id, decision):
    from veya.events.store import append_event

    if decision.get('grants') != []:
        raise ValueError('Verification cannot grant tool permissions')
    return append_event(connection, tenant, run_id, 'agent.verification', decision)
