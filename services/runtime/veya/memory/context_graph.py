"""A bounded view of actual memory/run/document relationships, not inferred authority."""

from collections import deque

from veya.domain.models import DomainError
from veya.ingestion.jobs import Documents
from veya.memory.store import Memories


def graph(db, tenant, run_id, owner='workspace_operator', max_nodes=50, max_depth=3):
    if (
        type(max_nodes) is not int
        or not 1 <= max_nodes <= 100
        or type(max_depth) is not int
        or not 0 <= max_depth <= 5
    ):
        raise DomainError('invalid_input', 'Graph traversal bounds required')
    db.get_run(tenant, run_id)
    memories = Memories(db, tenant, owner)
    permitted = {row['id']: row for row in memories.list()}
    nodes: list[dict] = []
    edges: list[dict] = []
    seen = set()
    queue = deque([('run', run_id, 0)])
    truncated = False
    while queue:
        kind, key, depth = queue.popleft()
        if (kind, key) in seen:
            continue
        if len(nodes) >= max_nodes:
            truncated = True
            break
        seen.add((kind, key))
        nodes.append({'kind': kind, 'id': key})
        if depth >= max_depth:
            truncated = True
            continue
        neighbours = []
        if kind == 'run':
            run = db.get_run(tenant, key)
            neighbours += [
                ('document', d['id'])
                for d in Documents(db, tenant).for_task(run.task.id)
                if d['state'] == 'ready'
            ]
            neighbours += [
                ('memory', a['id'])
                for a in memories.attribution(key)
                if a['available'] and a['id'] in permitted
            ]
        elif kind == 'memory' and key in permitted:
            neighbours.append(('run', permitted[key]['source_run']))
        for target_kind, target in neighbours[:max_nodes]:
            if len(edges) >= max_nodes * 2:
                truncated = True
                break
            edges.append({'from': key, 'to': target, 'relation': 'evidence'})
            queue.append((target_kind, target, depth + 1))
        truncated |= len(neighbours) > max_nodes
    ids = {n['id'] for n in nodes}
    return {
        'nodes': nodes,
        'edges': [e for e in edges if e['from'] in ids and e['to'] in ids],
        'truncated': truncated,
    }
