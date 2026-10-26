"""Authenticated operator settings. Credentials are write-only, never metadata."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from veya.providers.models import ModelConfig
from veya.providers.settings import Connections


class CheckInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    config: ModelConfig
    consent: bool = False


class ActivateInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    fingerprints: list[str] = Field(min_length=1, max_length=3)


class CredentialInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    reference: str = Field(pattern=r'^vault:[a-zA-Z0-9_-]{1,64}$')
    secret: SecretStr = Field(min_length=1, max_length=2048)


def router(connections: Connections):
    routes = APIRouter(prefix='/v1/connections')

    @routes.get('')
    def status() -> dict:
        return connections.status()

    @routes.post('/check')
    async def check(payload: CheckInput) -> dict:
        return await connections.check(payload.config, payload.consent)

    @routes.post('/activate')
    def activate(payload: ActivateInput) -> dict:
        return connections.activate(payload.fingerprints)

    @routes.post('/credential')
    def credential(payload: CredentialInput) -> dict:
        connections.vault.save(payload.reference, payload.secret.get_secret_value())
        return {'saved': True, 'reference': payload.reference}

    return routes
