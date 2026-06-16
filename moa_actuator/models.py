"""Pydantic data models for DoSA 2D and 3D designs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NodeModel(BaseModel):
    """A single node in the DoSA design tree (part, shape, test group, etc.)."""

    kind: str
    name: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    children: list["NodeModel"] = Field(default_factory=list)
    raw_lines: list[str] = Field(default_factory=list)


class TestModel(BaseModel):
    """A simulation test definition (Force, Stroke, Current)."""

    name: str
    kind: str
    properties: dict[str, Any] = Field(default_factory=dict)


class DesignModel(BaseModel):
    """Top-level design container parsed from a .dsa or .dsa3d file."""

    name: str = ""
    source_file: str = ""
    source_type: str = "unknown"  # "dsa" | "dsa3d"
    nodes: list[NodeModel] = Field(default_factory=list)
    parts: list[NodeModel] = Field(default_factory=list)
    tests: list[TestModel] = Field(default_factory=list)


NodeModel.model_rebuild()
