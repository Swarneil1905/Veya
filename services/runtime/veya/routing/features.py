"""Versioned pre-decision features with no labels, rewards or generated answers."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Features:
    instruction_bytes: int
    evidence_bytes: int
    document_count: int
    requires_tools: bool
    classification: str
    version: str = 'difficulty-v1'

    def __post_init__(self):
        for value in (self.instruction_bytes, self.evidence_bytes, self.document_count):
            if type(value) is not int or value < 0:
                raise ValueError('Features require nonnegative observed counts')
        if (
            self.instruction_bytes > 80000
            or self.evidence_bytes > 524288000
            or self.document_count > 1000
            or type(self.requires_tools) is not bool
            or self.classification not in {'restricted', 'internal'}
            or self.version != 'difficulty-v1'
        ):
            raise ValueError('Invalid feature contract')

    @property
    def context_bound(self):
        return self.instruction_bytes + min(self.evidence_bytes, 16384) + 4096


def extract(instruction, documents, *, classification='restricted'):
    if not isinstance(instruction, str):
        raise ValueError('Instruction must be text')
    return Features(
        len(instruction.encode()),
        sum(d['size'] for d in documents),
        len(documents),
        True,
        classification,
    )


def record(features):
    return asdict(features)
