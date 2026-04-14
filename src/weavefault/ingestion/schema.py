"""
WeaveFault data models.

All core data structures: Component, Edge, DiagramGraph, FMEARow, FMEADocument.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from weavefault.standards import canonical_standard_name, count_high_risk_rows


class WeaveFaultModel(BaseModel):
    """Compatibility wrapper for Pydantic v1/v2 serialization."""

    def model_dump(self, *args, **kwargs) -> dict[str, Any]:
        base = getattr(super(), "model_dump", None)
        if callable(base):
            return base(*args, **kwargs)
        kwargs.pop("mode", None)
        return self.dict(*args, **kwargs)


class ComponentType(str, Enum):
    """Types of components that can appear in an architecture diagram."""

    SERVICE = "SERVICE"
    DATABASE = "DATABASE"
    QUEUE = "QUEUE"
    GATEWAY = "GATEWAY"
    GATEWAY_EXTERNAL = "GATEWAY_EXTERNAL"
    SENSOR = "SENSOR"
    ACTUATOR = "ACTUATOR"
    NETWORK = "NETWORK"
    STORAGE = "STORAGE"
    CACHE = "CACHE"
    LOADBALANCER = "LOADBALANCER"
    UNKNOWN = "UNKNOWN"


class Component(WeaveFaultModel):
    """A single node in the architecture diagram."""

    id: str
    name: str
    component_type: ComponentType = ComponentType.UNKNOWN
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    x: float | None = None
    y: float | None = None
    is_external: bool = False
    is_critical: bool = False


class Edge(WeaveFaultModel):
    """A directed connection between two components."""

    source_id: str
    target_id: str
    label: str = ""
    bidirectional: bool = False
    data_flow: str = ""
    protocol: str = ""


class DiagramGraph(WeaveFaultModel):
    """
    The full parsed representation of an architecture diagram.

    Contains all extracted components and edges, plus metadata
    about the extraction quality and source.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    components: list[Component]
    edges: list[Edge]
    domain: str = "cloud"
    source_file: str = ""
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = 0.0
    raw_llm_response: str = ""

    @property
    def component_map(self) -> dict[str, Component]:
        """Return a mapping of component ID to Component."""
        return {component.id: component for component in self.components}

    @property
    def adjacency_list(self) -> dict[str, list[str]]:
        """Return a mapping of component ID to outgoing neighbour IDs."""
        adjacency: dict[str, list[str]] = {
            component.id: [] for component in self.components
        }
        for edge in self.edges:
            if edge.source_id in adjacency:
                adjacency[edge.source_id].append(edge.target_id)
            if edge.bidirectional and edge.target_id in adjacency:
                adjacency[edge.target_id].append(edge.source_id)
        return adjacency


class FMEARow(WeaveFaultModel):
    """A single FMEA entry for one failure mode of one component."""

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    component_id: str
    component_name: str
    failure_mode: str
    potential_effect: str
    cascade_effects: list[str] = Field(default_factory=list)
    severity: int = Field(ge=1, le=10)
    occurrence: int = Field(ge=1, le=10)
    detection: int = Field(ge=1, le=10)
    rpn: int = 0
    recommended_action: str = ""
    standard_clause: str = ""
    standard_metadata: dict[str, Any] = Field(default_factory=dict)
    reasoning_chain: str = ""
    confidence: float = 0.0
    generated_by: str = ""

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self.rpn = self.severity * self.occurrence * self.detection


class FMEADocument(WeaveFaultModel):
    """
    A complete FMEA document produced from one diagram analysis run.

    Contains all FMEARow entries, references to the original DiagramGraph,
    and summary statistics.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    diagram_graph: DiagramGraph
    rows: list[FMEARow]
    version: str = "1.0.0"
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    domain: str
    standard: str
    high_risk_threshold: int = 200
    total_components: int = 0
    high_risk_count: int = 0
    model_used: str = ""

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self.standard = canonical_standard_name(self.standard)
        self.total_components = len(self.diagram_graph.components)
        self.high_risk_count = count_high_risk_rows(
            self.rows,
            standard=self.standard,
            threshold=self.high_risk_threshold,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full document to a plain dictionary."""
        return self.model_dump(mode="json")

    def save(self, path: str) -> None:
        """
        Save the FMEA document to a .weavefault.json file.

        Args:
            path: Directory path or full file path. If a directory is given,
                the file will be named <document_id>.weavefault.json.
        """
        dest = Path(path)
        if dest.is_dir():
            dest = dest / f"{self.id}.weavefault.json"
        elif not dest.suffix:
            dest = dest.with_suffix(".weavefault.json")

        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2, default=str)
