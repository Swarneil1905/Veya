from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from veya.providers.usage import UsageStore
from veya.providers.models import PriceMetadata
from typing import Literal


class UsageSummary(BaseModel):
    calls:int
    unknown_calls:int
    complete:bool
    reported_costs:dict[str,str]
    estimated_costs:dict[str,str]


class UsageReport(BaseModel):
    status:Literal['completed','failed']
    reported_input:int|None
    reported_output:int|None
    source:Literal['provider_reported']


class UsageCall(BaseModel):
    model_config = ConfigDict(protected_namespaces=('model_validate', 'model_dump'))
    call_id:str
    model_config_id:str
    provider_id:str
    model_name:str
    config_hash:str
    price:PriceMetadata|None
    price_version:str|None
    estimated_input:int|None
    estimated_output:int|None
    report:UsageReport|None
    reported_cost:str|None


class UsagePage(BaseModel):
    items:list[UsageCall]
    next_cursor:int|None


def router(db,tenant):
    routes=APIRouter();store=UsageStore(db)
    @routes.get('/v1/runs/{run_id}/usage',response_model=UsageSummary)
    def summary(run_id:str):
        return store.summary(tenant,run_id)
    @routes.get('/v1/runs/{run_id}/usage/calls',response_model=UsagePage)
    def calls(run_id:str,after:int=Query(0,ge=0,le=2**63-1),limit:int=Query(50,ge=1,le=100)):
        return store.page(tenant,run_id,after=after,limit=limit)
    return routes
