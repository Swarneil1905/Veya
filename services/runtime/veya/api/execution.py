from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from veya.domain.models import Run


class StartInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expected_selection: list[str] = Field(min_length=1, max_length=3)
    allow_remote: bool = False


def router(agent):
    routes = APIRouter(prefix='/v1/runs')

    @routes.post('/{run_id}/execute', response_model=Run)
    async def start(run_id: str, payload: StartInput):
        return await agent.start(run_id, payload.expected_selection, payload.allow_remote)

    @routes.post('/{run_id}/cancel', response_model=Run)
    async def cancel(run_id: str):
        return agent.cancel(run_id)

    return routes
