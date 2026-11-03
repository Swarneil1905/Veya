"""Explicit indexing checkpoints and deletion propagation; grants remain authoritative."""

from veya.retrieval.embeddings import Embeddings


def reindex(db, tenant, document_id, **kwargs):
    return Embeddings(db, tenant, **kwargs).index(document_id)


def purge(connection, tenant, document_id):
    rows = connection.execute(
        'SELECT model,chunks FROM retrieval_indexes WHERE tenant_id=? AND document_id=?',
        (tenant, document_id),
    ).fetchall()
    connection.execute(
        'DELETE FROM retrieval_indexes WHERE tenant_id=? AND document_id=?', (tenant, document_id)
    )
    # Remove cached embeddings for the revoked content even when another index used it.
    # Those indexes are invalidated so no partially deleted index can be read.
    for row in rows:
        connection.execute(
            'DELETE FROM retrieval_vectors WHERE tenant_id=? AND model=?', (tenant, row['model'])
        )
        connection.execute(
            "UPDATE retrieval_indexes SET state='failed',error='source_revoked' WHERE tenant_id=? AND model=?",
            (tenant, row['model']),
        )
    connection.execute('DELETE FROM inference_cache WHERE tenant_id=?', (tenant,))
