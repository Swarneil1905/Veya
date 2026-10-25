from fastapi import APIRouter
from pydantic import BaseModel

from veya.tools.registry import Effect, ToolRegistry, ToolScope


class ToolManifest(BaseModel):
    name: str
    version: str
    description: str
    effect: Effect
    capabilities: list[str]
    input_schema: dict
    output_schema: dict
    max_input_bytes: int
    max_output_bytes: int


def router(registry: ToolRegistry, scope: ToolScope) -> APIRouter:
    routes = APIRouter(prefix='/v1')

    @routes.get('/tools', response_model=list[ToolManifest])
    def list_tools() -> list[dict]:
        return registry.available(scope)

    return routes
