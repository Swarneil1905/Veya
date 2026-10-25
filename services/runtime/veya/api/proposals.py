from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from veya.storage.sqlite import Database
from veya.tools.proposals import Proposal, ProposalStore
from veya.tools.registry import ToolRegistry, ToolScope


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    tool_name: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    tool_version: str = Field(max_length=32)
    arguments: dict


def display(proposal: Proposal) -> dict:
    return {key: value for key, value in vars(proposal).items() if key != 'arguments_json'} | {
        'arguments': proposal.arguments
    }


def router(db: Database, registry: ToolRegistry, scope: ToolScope) -> APIRouter:
    routes = APIRouter()
    store = ProposalStore(db, registry)

    @routes.post('/v1/runs/{run_id}/proposals', status_code=201)
    def plan(run_id: str, request: PlanRequest):
        # A malformed path is a request error, not an uncaught domain constructor error.
        from veya.domain.models import DomainError, identifier

        try:
            identifier(run_id)
        except ValueError as error:
            raise DomainError('invalid_input', 'Invalid run identifier') from error
        return display(
            store.plan(scope, run_id, request.tool_name, request.tool_version, request.arguments)
        )

    @routes.get('/v1/proposals/{proposal_id}')
    def review(proposal_id: str):
        return display(store.get(scope.tenant_id, proposal_id))

    return routes
