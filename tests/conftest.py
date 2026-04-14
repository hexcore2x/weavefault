"""
Shared pytest fixtures for WeaveFault tests.

These fixtures provide reusable test data so individual test modules
don't repeat the same boilerplate setup code.
"""
from __future__ import annotations

import pytest

from weavefault.graph.builder import GraphBuilder
from weavefault.graph.propagation import CascadeSimulator
from weavefault.ingestion.schema import (
    Component,
    ComponentType,
    DiagramGraph,
    Edge,
    FMEADocument,
    FMEARow,
)


# ── Diagrams ──────────────────────────────────────────────────────────────────


@pytest.fixture
def minimal_diagram() -> DiagramGraph:
    """Single node, no edges."""
    return DiagramGraph(
        components=[
            Component(id="svc", name="Service", component_type=ComponentType.SERVICE)
        ],
        edges=[],
        domain="cloud",
        confidence=1.0,
    )


@pytest.fixture
def three_node_diagram() -> DiagramGraph:
    """Gateway → Service → Database linear chain."""
    return DiagramGraph(
        components=[
            Component(
                id="gateway", name="API Gateway", component_type=ComponentType.GATEWAY
            ),
            Component(
                id="service", name="Auth Service", component_type=ComponentType.SERVICE
            ),
            Component(id="db", name="User DB", component_type=ComponentType.DATABASE),
        ],
        edges=[
            Edge(
                source_id="gateway", target_id="service", label="auth", protocol="HTTP"
            ),
            Edge(source_id="service", target_id="db", label="query", protocol="TCP"),
        ],
        domain="cloud",
        confidence=0.9,
    )


@pytest.fixture
def star_diagram() -> DiagramGraph:
    """Hub with 3 spokes — hub is a SPOF."""
    return DiagramGraph(
        components=[
            Component(id="hub", name="Hub", component_type=ComponentType.SERVICE),
            Component(
                id="spoke_a", name="Spoke A", component_type=ComponentType.SERVICE
            ),
            Component(
                id="spoke_b", name="Spoke B", component_type=ComponentType.SERVICE
            ),
            Component(
                id="spoke_c", name="Spoke C", component_type=ComponentType.SERVICE
            ),
        ],
        edges=[
            Edge(source_id="hub", target_id="spoke_a"),
            Edge(source_id="hub", target_id="spoke_b"),
            Edge(source_id="hub", target_id="spoke_c"),
        ],
        domain="cloud",
        confidence=1.0,
    )


@pytest.fixture
def cloud_diagram() -> DiagramGraph:
    """Full 6-node e-commerce checkout architecture."""
    return DiagramGraph(
        components=[
            Component(
                id="api_gateway",
                name="API Gateway",
                component_type=ComponentType.GATEWAY,
            ),
            Component(
                id="auth_service",
                name="Auth Service",
                component_type=ComponentType.SERVICE,
            ),
            Component(
                id="order_service",
                name="Order Service",
                component_type=ComponentType.SERVICE,
            ),
            Component(
                id="payment_service",
                name="Payment Service",
                component_type=ComponentType.SERVICE,
            ),
            Component(
                id="order_db", name="Orders DB", component_type=ComponentType.DATABASE
            ),
            Component(
                id="event_queue", name="Event Queue", component_type=ComponentType.QUEUE
            ),
        ],
        edges=[
            Edge(source_id="api_gateway", target_id="auth_service", protocol="HTTP"),
            Edge(source_id="api_gateway", target_id="order_service", protocol="HTTP"),
            Edge(
                source_id="order_service", target_id="payment_service", protocol="gRPC"
            ),
            Edge(source_id="order_service", target_id="order_db", protocol="TCP"),
            Edge(source_id="order_service", target_id="event_queue", protocol="TCP"),
            Edge(source_id="payment_service", target_id="event_queue", protocol="TCP"),
        ],
        domain="cloud",
        confidence=0.95,
    )


# ── Graphs ────────────────────────────────────────────────────────────────────


@pytest.fixture
def three_node_graph(three_node_diagram):
    return GraphBuilder().build(three_node_diagram)


@pytest.fixture
def cloud_graph(cloud_diagram):
    return GraphBuilder().build(cloud_diagram)


@pytest.fixture
def star_graph(star_diagram):
    return GraphBuilder().build(star_diagram)


# ── Cascade results ───────────────────────────────────────────────────────────


@pytest.fixture
def three_node_cascades(three_node_graph):
    return CascadeSimulator().simulate_all(three_node_graph)


@pytest.fixture
def cloud_cascades(cloud_graph):
    return CascadeSimulator().simulate_all(cloud_graph)


# ── FMEA rows ─────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_row() -> FMEARow:
    return FMEARow(
        component_id="gateway",
        component_name="API Gateway",
        failure_mode="TLS certificate expiry",
        potential_effect="All HTTPS traffic rejected",
        cascade_effects=["Auth Service", "Order Service"],
        severity=9,
        occurrence=3,
        detection=6,
        recommended_action="Automate cert rotation",
        standard_clause="IEC 60812 Clause 7.4",
        reasoning_chain="Severity=9 because all traffic blocked.",
        confidence=0.95,
        generated_by="test",
    )


@pytest.fixture
def sample_row_low_risk() -> FMEARow:
    return FMEARow(
        component_id="db",
        component_name="User DB",
        failure_mode="Slow query log growing large",
        potential_effect="Disk space warning",
        cascade_effects=[],
        severity=2,
        occurrence=3,
        detection=2,
        recommended_action="Rotate slow query log weekly",
        confidence=0.8,
        generated_by="test",
    )


@pytest.fixture
def sample_rows(sample_row, sample_row_low_risk) -> list[FMEARow]:
    return [sample_row, sample_row_low_risk]


# ── Documents ─────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_document(three_node_diagram, sample_rows) -> FMEADocument:
    return FMEADocument(
        diagram_graph=three_node_diagram,
        rows=sample_rows,
        domain="cloud",
        standard="IEC_60812",
        model_used="test-model",
    )
