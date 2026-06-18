from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NodeModel(BaseModel):
    kind: str
    name: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    children: list["NodeModel"] = Field(default_factory=list)
    raw_lines: list[str] = Field(default_factory=list)


class TestModel(BaseModel):
    name: str
    kind: str
    properties: dict[str, Any] = Field(default_factory=dict)


class DesignModel(BaseModel):
    name: str = ""
    source_file: str = ""
    source_type: str = "unknown"
    nodes: list[NodeModel] = Field(default_factory=list)
    parts: list[NodeModel] = Field(default_factory=list)
    tests: list[TestModel] = Field(default_factory=list)


NodeModel.model_rebuild()
