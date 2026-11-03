"""Filter before ranking and recheck immediately before context consumption."""

from datetime import datetime, timezone

from veya.domain.models import DomainError
from veya.ingestion.jobs import Documents


def allowed_documents(db, tenant, task_id, at=None):
    now = at or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise DomainError('invalid_input', 'Evidence time requires a timezone')
    db.get_task(tenant, task_id)
    return {
        item['id']: item
        for item in Documents(db, tenant).for_task(task_id)
        if item['state'] == 'ready' and datetime.fromisoformat(item['effective_at']) <= now
    }


def permitted_items(db, tenant, task_id, items, at=None):
    allowed = allowed_documents(db, tenant, task_id, at)
    return [
        item
        for item in items
        if item['citation'].split(':')[0] in allowed
        and item['version'] == allowed[item['citation'].split(':')[0]]['version']
    ]
