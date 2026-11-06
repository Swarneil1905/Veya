"""Withdraw source permission and identify affected datasets and model lineage."""

from veya.domain.models import DomainError, identifier

from training.data.manifest import Manifest, validate_current


def register_dataset(store, manifest):
    with store.db.transaction() as connection:
        validate_current(store, manifest)
        connection.execute(
            'INSERT OR IGNORE INTO dataset_lineage VALUES (?,?,?,0)',
            (store.tenant, manifest.fingerprint, manifest.model_dump_json()),
        )
    return manifest.fingerprint


def register_model(store, model_id, dataset_fingerprint):
    identifier(model_id)
    with store.db.transaction() as connection:
        row = connection.execute(
            'SELECT withdrawn,manifest_json FROM dataset_lineage '
            'WHERE tenant_id=? AND fingerprint=?',
            (store.tenant, dataset_fingerprint),
        ).fetchone()
        if row is None or row[0]:
            raise DomainError('forbidden', 'Dataset is missing or withdrawn')
        validate_current(store, Manifest.model_validate_json(row['manifest_json']))
        connection.execute(
            'INSERT OR IGNORE INTO model_lineage VALUES (?,?,?,0)',
            (store.tenant, model_id, dataset_fingerprint),
        )


def withdraw(store, source_id):
    # The canonical authorization path propagates withdrawal atomically.
    store.authorize(source_id, False)
    with store.db.connection() as connection:
        return {
            'source_id': source_id,
            'models_requiring_review': [
                row[0]
                for row in connection.execute(
                    'SELECT DISTINCT model_id FROM model_lineage '
                    'WHERE tenant_id=? AND requires_review=1 ORDER BY model_id',
                    (store.tenant,),
                )
            ],
            'model_untraining_claimed': False,
        }
