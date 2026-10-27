"""Logical time only; missing scenario facts never become invented answers."""

import hashlib
from typing import Literal

from pydantic import Field
from veya.finance.models import Value


class Answer(Value):
    question: str = Field(min_length=1, max_length=200)
    answer: str = Field(min_length=1, max_length=2000)


class Scenario(Value):
    seed: int = Field(ge=0, lt=2**32)
    behavior: Literal['cooperative', 'delayed', 'abandon']
    max_delay: int = Field(default=300, ge=1, le=86400)
    facts: tuple[Answer, ...] = Field(max_length=100)


class Simulator:
    def __init__(self, scenario: Scenario):
        self.scenario = Scenario.model_validate_json(scenario.model_dump_json())
        self.answers = {a.question: a.answer for a in self.scenario.facts}
        if len(self.answers) != len(self.scenario.facts):
            raise ValueError('Duplicate question facts')
        self.events = {}

    def ask(self, request_id: str, question: str, *, at: int):
        if type(at) is not int or at < 0 or not request_id or len(request_id) > 100:
            raise ValueError('Invalid event')
        key = (request_id, question, at)
        if request_id in self.events:
            previous, event = self.events[request_id]
            if previous != key:
                raise ValueError('Request identity changed')
            return dict(event)
        delay = (
            0
            if self.scenario.behavior == 'cooperative'
            else 1
            + int.from_bytes(
                hashlib.sha256(f'{self.scenario.seed}:{request_id}'.encode()).digest()[:4], 'big'
            )
            % self.scenario.max_delay
        )
        kind = (
            'abandoned'
            if self.scenario.behavior == 'abandon'
            else 'answered'
            if question in self.answers
            else 'unavailable'
        )
        event = {
            'request_id': request_id,
            'at': at + delay,
            'kind': kind,
            'answer': self.answers.get(question) if kind == 'answered' else None,
        }
        self.events[request_id] = (key, event)
        return dict(event)
