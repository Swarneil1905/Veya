"""Persist a conservative wall-clock high-water mark for approval validity."""

import math

from veya.domain.models import DomainError


def observe(conn, tenant: str, workspace: str, now: float) -> float:
    if type(now) not in {int, float} or not math.isfinite(now):
        raise DomainError('conflict', 'Review clock is unavailable')
    row = conn.execute(
        'SELECT observed_at FROM approval_clocks WHERE tenant_id=? AND workspace_id=?',
        (tenant, workspace),
    ).fetchone()
    result = max(now, row[0]) if row else now
    conn.execute(
        'INSERT INTO approval_clocks VALUES (?,?,?) ON CONFLICT(tenant_id,workspace_id) DO UPDATE SET observed_at=excluded.observed_at',
        (tenant, workspace, result),
    )
    return result
