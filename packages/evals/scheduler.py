"""Durable bounded jobs; expired leases are recorded, fenced and explicitly retried."""

import asyncio
import time

from pydantic import Field
from veya.domain.models import DomainError, identifier
from veya.finance.models import Value
from veya.research.models import Outcome, fingerprint


class Job(Value):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    case_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    candidate: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    repetition: int = Field(ge=0, le=99)
    seed: int = Field(ge=0, lt=2**32)


class Scheduler:
    def __init__(self, db, tenant, *, clock=time.time):
        identifier(tenant)
        self.db, self.tenant, self.clock = db, tenant, clock

    def plan(self, evaluation_id, jobs: tuple[Job, ...], spec_hash: str):
        identifier(evaluation_id)
        jobs = tuple(Job.model_validate_json(j.model_dump_json()) for j in jobs)
        if not 1 <= len(jobs) <= 10000 or len({j.id for j in jobs}) != len(jobs):
            raise ValueError('Unique bounded jobs required')
        if len({(j.case_id, j.candidate, j.repetition) for j in jobs}) != len(jobs):
            raise ValueError('Duplicate repetition')
        if len(spec_hash) != 64 or any(c not in '0123456789abcdef' for c in spec_hash):
            raise ValueError('Spec fingerprint required')
        digest = fingerprint(
            {'spec': spec_hash, 'jobs': [j.model_dump() for j in sorted(jobs, key=lambda j: j.id)]}
        )
        with self.db.transaction() as c:
            prior = c.execute(
                'SELECT plan_hash FROM evaluation_jobs WHERE tenant_id=? AND evaluation_id=?',
                (self.tenant, evaluation_id),
            ).fetchall()
            if prior:
                if len(prior) != len(jobs) or any(r[0] != digest for r in prior):
                    raise DomainError('conflict', 'Evaluation plan changed')
                return
            c.executemany(
                "INSERT INTO evaluation_jobs(tenant_id,evaluation_id,id,plan_hash,payload,state) VALUES (?,?,?,?,?,'pending')",
                [(self.tenant, evaluation_id, j.id, digest, j.model_dump_json()) for j in jobs],
            )

    def claim(self, evaluation_id, lease_seconds=120):
        identifier(evaluation_id)
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 600:
            raise ValueError('Bounded lease required')
        now = self.clock()
        with self.db.transaction() as c:
            row = c.execute(
                "SELECT * FROM evaluation_jobs WHERE tenant_id=? AND evaluation_id=? AND (state='pending' OR (state='running' AND lease_until<=?)) ORDER BY id LIMIT 1",
                (self.tenant, evaluation_id, now),
            ).fetchone()
            if row is None:
                return None
            if row['state'] == 'running':
                c.execute(
                    'INSERT INTO evaluation_attempts VALUES (?,?,?,?,?)',
                    (self.tenant, evaluation_id, row['id'], row['generation'], 'lease_expired'),
                )
            generation = row['generation'] + 1
            c.execute(
                "UPDATE evaluation_jobs SET state='running',generation=?,lease_until=? WHERE tenant_id=? AND evaluation_id=? AND id=?",
                (generation, now + lease_seconds, self.tenant, evaluation_id, row['id']),
            )
        return Job.model_validate_json(row['payload']), generation

    def finish(self, evaluation_id, job_id, generation, result: Outcome):
        result = Outcome.model_validate_json(result.model_dump_json())
        with self.db.transaction() as c:
            row = c.execute(
                'SELECT * FROM evaluation_jobs WHERE tenant_id=? AND evaluation_id=? AND id=?',
                (self.tenant, evaluation_id, job_id),
            ).fetchone()
            if (
                row is None
                or row['state'] != 'running'
                or row['generation'] != generation
                or row['lease_until'] <= self.clock()
            ):
                raise DomainError('conflict', 'Worker lease no longer owns this repetition')
            job = Job.model_validate_json(row['payload'])
            if (result.id, result.case_id, result.candidate, result.repetition, result.seed) != (
                job.id,
                job.case_id,
                job.candidate,
                job.repetition,
                job.seed,
            ):
                raise ValueError('Outcome does not match job')
            c.execute(
                "UPDATE evaluation_jobs SET state='finished',result=?,lease_until=0 WHERE tenant_id=? AND evaluation_id=? AND id=?",
                (result.model_dump_json(), self.tenant, evaluation_id, job_id),
            )
            c.execute(
                'INSERT INTO evaluation_attempts VALUES (?,?,?,?,?)',
                (self.tenant, evaluation_id, job_id, generation, result.status),
            )

    def report(self, evaluation_id):
        with self.db.connection() as c:
            jobs = c.execute(
                'SELECT id,state,result FROM evaluation_jobs WHERE tenant_id=? AND evaluation_id=? ORDER BY id',
                (self.tenant, evaluation_id),
            ).fetchall()
            attempts = [
                dict(r)
                for r in c.execute(
                    'SELECT job_id,generation,outcome FROM evaluation_attempts WHERE tenant_id=? AND evaluation_id=? ORDER BY job_id,generation',
                    (self.tenant, evaluation_id),
                )
            ]
        return {
            'expected': tuple(r['id'] for r in jobs),
            'outcomes': tuple(
                Outcome.model_validate_json(r['result']) for r in jobs if r['result']
            ),
            'unfinished': [r['id'] for r in jobs if r['state'] != 'finished'],
            'attempts': attempts,
        }


async def work(scheduler, evaluation_id, execute, failure, *, limit=100, timeout_seconds=90):
    """Run a bounded slice. execute owns a fresh environment; crash leases remain resumable.

    failure is a trusted host projection of this exact job, never exception text or model output.
    """
    if (
        type(limit) is not int
        or not 1 <= limit <= 1000
        or type(timeout_seconds) is not int
        or not 1 <= timeout_seconds <= 590
    ):
        raise ValueError('Bounded worker budget required')
    for _ in range(limit):
        claimed = scheduler.claim(evaluation_id, timeout_seconds + 10)
        if claimed is None:
            break
        job, generation = claimed
        try:
            result = await asyncio.wait_for(execute(job), timeout=timeout_seconds)
            result = Outcome.model_validate_json(result.model_dump_json())
        except Exception:
            result = failure(job)
            if result.status != 'system_failure':
                raise ValueError('Worker failures cannot become successes')
        scheduler.finish(evaluation_id, job.id, generation, result)
    return scheduler.report(evaluation_id)
