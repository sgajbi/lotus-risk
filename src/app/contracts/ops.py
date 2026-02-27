from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OpsChecks(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    live: bool
    ready: bool
    draining: bool


class OpsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    service: str
    version: str
    status: str
    checks: OpsChecks
    input_modes: list[str] = Field(alias="inputModes")
