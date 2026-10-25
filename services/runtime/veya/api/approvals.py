import hashlib
import secrets
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from veya.domain.models import DomainError
from veya.policy.inbox import ApprovalInbox


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    revision: int = Field(ge=1)
    decision: Literal['approve', 'reject']
    note: str = Field(min_length=1, max_length=2000)


class ReviewSummary(BaseModel):
    id: str
    proposal_id: str
    operation_key: str
    expires_at: float
    state: Literal['pending', 'approved', 'rejected', 'superseded']
    revision: int
    receipt_id: str | None
    policy_version: str
    expired: bool
    attention: Literal['normal', 'due_soon', 'expired']


class ReviewDetail(ReviewSummary):
    arguments: dict
    tool_name: str
    tool_version: str
    arguments_hash: str
    note: str | None
    run_id: str
    scope: dict[str, str]
    context_hash: str
    policy_reason: str


class ReviewPage(BaseModel):
    items: list[ReviewSummary]
    next_cursor: int | None


def router(inbox: ApprovalInbox | None, reviewer_token: str | None) -> APIRouter:
    expected = hashlib.sha256((reviewer_token or '').encode()).digest()

    def authorize(request: Request):
        supplied = hashlib.sha256(
            request.headers.get('x-veya-reviewer-token', '').encode()
        ).digest()
        if inbox is None or not reviewer_token or not secrets.compare_digest(expected, supplied):
            raise DomainError(
                'forbidden', 'A separately authenticated reviewer session is required'
            )

    routes = APIRouter(dependencies=[Depends(authorize)])

    @routes.get('/v1/approvals', response_model=ReviewPage)
    def pending(after: int = Query(0, ge=0, le=2**63 - 1), limit: int = Query(50, ge=1, le=100)):
        assert inbox is not None
        return inbox.pending(after=after, limit=limit)

    @routes.get('/v1/approvals/{item_id}', response_model=ReviewDetail)
    def detail(item_id: str):
        assert inbox is not None
        return inbox.get(item_id)

    @routes.post('/v1/approvals/{item_id}/decision', response_model=ReviewDetail)
    def decide(item_id: str, body: DecisionRequest):
        assert inbox is not None
        return inbox.decide(item_id, body.revision, body.decision, body.note)

    return routes
