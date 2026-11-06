"""Propagate revoked source access to registered dataset and model lineage."""

import json


def affected(connection, tenant, source_id):
    datasets = []
    for row in connection.execute(
        'SELECT fingerprint,manifest_json FROM dataset_lineage WHERE tenant_id=?', (tenant,)
    ):
        manifest = json.loads(row['manifest_json'])
        if any(source_id in item['source_ids'] for item in manifest['rows']):
            datasets.append(row['fingerprint'])
    for digest in datasets:
        connection.execute(
            'UPDATE dataset_lineage SET withdrawn=1 WHERE tenant_id=? AND fingerprint=?',
            (tenant, digest),
        )
        connection.execute(
            'UPDATE model_lineage SET requires_review=1 '
            'WHERE tenant_id=? AND dataset_fingerprint=?',
            (tenant, digest),
        )
    return datasets
