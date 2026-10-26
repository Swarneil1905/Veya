"""Everything affecting a run is explicit and content-addressed; no mutable model aliases."""

import hashlib
from typing import Literal

from pydantic import Field, model_validator
from veya.finance.models import Value
from veya.providers.models import ModelConfig
from veya.tools.contracts import canonical_json

from packages.environments.splits import Entry, SplitManifest

GraderName = Literal['state', 'arithmetic', 'citation', 'policy']


class TaskInputs(Value):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    instruction_fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    expected_state_fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')

    @classmethod
    def pin(cls, task_id, instruction, expected_state):
        if type(instruction) is not str or not 1 <= len(instruction) <= 8000:
            raise ValueError('A bounded task instruction is required')
        return cls(
            id=task_id,
            instruction_fingerprint=hashlib.sha256(instruction.encode()).hexdigest(),
            expected_state_fingerprint=hashlib.sha256(
                canonical_json(expected_state, 1048576).encode()
            ).hexdigest(),
        )


class EvaluationSpec(Value):
    schema_version: Literal[1] = 1
    tasks: tuple[Entry, ...] = Field(min_length=1, max_length=1000)
    inputs: tuple[TaskInputs, ...] = Field(min_length=1, max_length=1000)
    split_fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    model: ModelConfig
    model_revision: str = Field(pattern=r'^sha256:[a-f0-9]{64}$')
    harness_version: str = Field(min_length=1, max_length=100)
    intervention_version: str = Field(min_length=1, max_length=100)
    seeds: tuple[int, ...] = Field(min_length=1, max_length=100)
    graders: tuple[GraderName, ...] = Field(min_length=1, max_length=4)

    @model_validator(mode='after')
    def explicit(self):
        SplitManifest(seed=0, entries=self.tasks)
        if len(self.inputs) != len(self.tasks) or {i.id for i in self.inputs} != {
            t.id for t in self.tasks
        }:
            raise ValueError('Pin instruction and grading inputs for each task exactly once')
        cap = self.model.capabilities
        if (
            cap.tools is not True
            or cap.streaming is not True
            or cap.context_tokens is None
            or cap.max_output_tokens is None
        ):
            raise ValueError('Explicit supported provider capabilities required')
        if len(set(self.seeds)) != len(self.seeds) or any(not 0 <= s < 2**32 for s in self.seeds):
            raise ValueError('Unique bounded seeds required')
        if len(set(self.graders)) != len(self.graders):
            raise ValueError('Duplicate grader')
        return self

    @property
    def fingerprint(self):
        return hashlib.sha256(
            canonical_json(self.model_dump(mode='json'), 1048576).encode()
        ).hexdigest()
