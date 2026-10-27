"""Controlled invoice amounts retain parent lineage; held-out templates cannot generate training rows."""

from veya.finance.matching import match
from veya.research.models import fingerprint

from packages.environments.invoices.scenarios import shortage
from packages.environments.snapshot import Snapshot
from packages.environments.splits import SplitManifest


def variants(parent, manifest: SplitManifest, values):
    parent = Snapshot.model_validate_json(parent.model_dump_json())
    # This generator only supports the explicit shortage template; never silently replace another task.
    base, _ = shortage(
        case_id=parent.case_id,
        billed=parent.invoice.lines[0].quantity,
        received=parent.receipts[0].quantity,
        price=parent.invoice.lines[0].unit_price.amount,
    )
    if base.model_dump(exclude={'family', 'lineage'}) != parent.model_dump(
        exclude={'family', 'lineage'}
    ):
        raise ValueError('Unsupported augmentation template')
    entry = next((e for e in manifest.entries if e.id == parent.case_id), None)
    if (
        entry is None
        or entry.split != 'train'
        or entry.fingerprint != parent.fingerprint
        or entry.family != parent.family
        or entry.lineage != parent.lineage
    ):
        raise ValueError('Only pinned training templates can be augmented')
    if not 1 <= len(values) <= 100:
        raise ValueError('Bounded variants required')
    result = []
    for index, (billed, received, price) in enumerate(values):
        snapshot, blobs = shortage(
            billed=billed,
            received=received,
            price=price,
            case_id='fixture_variant_'
            + fingerprint(
                {'parent': parent.fingerprint, 'values': [billed, received, price], 'index': index}
            )[:32],
        )
        snapshot = Snapshot.model_validate_json(
            snapshot.model_copy(
                update={'family': parent.family, 'lineage': parent.lineage}
            ).model_dump_json()
        )
        matched = match(snapshot.invoice, snapshot.order, snapshot.receipts)
        if matched.discrepancy is None:
            raise ValueError('Unverifiable synthetic arithmetic')
        result.append((snapshot, blobs, matched))
    return result
