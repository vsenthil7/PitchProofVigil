"""Golden-dataset API schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CreateDatasetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    examples: list[dict] = Field(default_factory=list)


class DatasetResponse(BaseModel):
    id: str
    name: str
    description: str
    example_count: int
