"""Create-only reviewed corpus export. Authorization is rechecked under the workspace writer lock.

This is a scrubbed research corpus, not a tokenizer-specific training dataset (VEY-159).
"""

import json
from pathlib import Path

from veya.research.models import fingerprint
from veya.tools.contracts import canonical_json

from training.data.deduplicate import Example, deduplicate
from training.data.manifest import build, validate_current
from training.data.quality import diagnose
from training.data.redact import scrub


def export(store, path: Path, ids: tuple[str, ...], *, rules, held_out: tuple[Example, ...]):
    if len(ids) > 300:
        raise ValueError('Corpus export is bounded to 300 review rows')
    # Lineage cannot silently reintroduce a scrubbed identifier. A public corpus must
    # explicitly permit its linkage fields; otherwise keep the entire export local/unwritten.
    policies = {r.path: r.classification for r in rules}
    for key in ('id', 'source_ids[]', 'events[].run_id', 'reviewer'):
        if policies.get(key) != 'public':
            raise ValueError('Required lineage identity is not classified public')
    transforms = (
        'normalize-v1',
        'scrub:' + fingerprint([r.model_dump(mode='json') for r in rules]),
        'dedup-v1',
    )
    with store.db.transaction():
        manifest = build(store, ids, transforms)
        cleaned = {}
        examples = []
        diagnostics = []
        for row in manifest.rows:
            value = store.trajectory(row.id)['trace']
            if row.split != 'train':
                raise ValueError('Held-out rows cannot enter a training corpus')
            result = scrub(value, rules)
            if result['requires_review']:
                raise ValueError('Unclassified fields require review before export')
            sanitized = result['record']
            try:
                unchanged = (
                    sanitized['id'] == value['id']
                    and sanitized['source_ids'] == value['source_ids']
                    and [e['run_id'] for e in sanitized['events']]
                    == [e['run_id'] for e in value['events']]
                )
            except (KeyError, TypeError):
                unchanged = False
            reviewer = scrub({'reviewer': row.reviewer}, rules)['record'].get('reviewer')
            if not unchanged or reviewer != row.reviewer:
                raise ValueError('Scrubbed provenance cannot be restored by lineage metadata')
            cleaned[row.id] = result['record']
            text = json.dumps(result['record']['events'], sort_keys=True)
            examples.append(
                Example(
                    id=row.id,
                    family=value['family'],
                    split=row.split,
                    text=text,
                    semantic_key=fingerprint(text),
                )
            )
            diagnostics.append(
                {**row.model_dump(mode='json'), 'family': value['family'], 'authorized': True}
            )
        duplicates = deduplicate(tuple(examples) + held_out)
        if set(ids) & set(duplicates['quarantined']):
            raise ValueError('Held-out neighbor requires quarantine')
        retained = tuple(key for key in ids if key in duplicates['kept'])
        if not retained:
            raise ValueError('No eligible unique examples')
        manifest = build(store, retained, transforms)
        quality = diagnose(
            expected_ids=retained,
            rows=[r for r in diagnostics if r['id'] in retained],
            stage_results={
                s: 'passed'
                for s in ('normalization', 'redaction', 'review', 'lineage', 'deduplication')
            },
        )
        if not quality['passed']:
            raise ValueError('Quality diagnostics block export')
        validate_current(store, manifest)
        payload = {
            'schema_version': 1,
            'format': 'reviewed_research_corpus',
            'manifest': manifest.model_dump(mode='json'),
            'records': [cleaned[key] for key in retained],
            'quality': quality,
            'deduplication': {
                'input_count': len(ids),
                'kept': list(retained),
                'removed': {
                    key: value for key, value in duplicates['removed'].items() if key in ids
                },
                'quarantined': [],
                'unique_families': quality['family_count'],
            },
        }
        encoded = canonical_json(payload, 1048576)
        with path.open('x', encoding='utf8', newline='\n') as output:
            output.write(encoded + '\n')
    return {'rows': len(retained), 'fingerprint': fingerprint(payload), 'training_ready': False}
