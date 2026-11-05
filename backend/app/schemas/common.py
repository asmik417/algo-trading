"""Shared schema pieces: the base model config, ISO date type, and the param value type.
Every schema module builds on these so request/response shapes stay consistent with docs/API_CONTRACT.md.
"""
from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer

ParamValue = float | int | bool | str | list[str]
Params = dict[str, ParamValue]

# Accepts "2027-02-15" on input (400 on anything else) and always serialises back to that string.
IsoDate = Annotated[date, PlainSerializer(lambda d: d.isoformat(), return_type=str)]


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(ApiModel):
    detail: str
