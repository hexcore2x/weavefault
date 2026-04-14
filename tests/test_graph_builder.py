"""
Tests for GraphBuilder — build, adjacency summary, critical nodes, Mermaid export.
"""

from __future__ import annotations

import pytest

from weavefault.graph.builder import GraphBuilder
from weavefault.ingestion.schema import Component, ComponentType, DiagramGraph, Edge


def _make_diagram() -> DiagramGraph:
    """Return a small 3-node cloud diagram for testing."""
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
def builder() -> GraphBuilder:
    return GraphBuilder()


@pytest.fixture
def diagram() -> DiagramGraph:
    return _make_diagram()


class TestBuild:
    def test_returns_digraph(self, builder, diagram) -> None:
        import networkx as nx

        graph = builder.build(diagram)
        assert isinstance(graph, nx.DiGraph)

    def test_node_count(self, builder, diagram) -> None:
        graph = builder.build(diagram)
        assert graph.number_of_nodes() == 3

    def test_edge_count(self, builder, diagram) -> None:
        graph = builder.build(diagram)
        assert graph.number_of_edges() == 2

    def test_node_attributes_set(self, builder, diagram) -> None:
        graph = builder.build(diagram)
        assert graph.nodes["gateway"]["name"] == "API Gateway"
        assert graph.nodes["gateway"]["component_type"] == "GATEWAY"

    def test_betweenness_centrality_computed(self, builder, diagram) -> None:
        graph = builder.build(diagram)
        for node_id in graph.nodes:
            assert "betweenness_centrality" in graph.nodes[node_id]

    def test_in_out_degree_stored(self, builder, diagram) -> None:
        graph = builder.build(diagram)
        assert graph.nodes["service"]["in_degree"] == 1
        assert graph.nodes["service"]["out_degree"] == 1

    def test_isolated_flag_set(self, builder) -> None:
        isolated_diagram = DiagramGraph(
            components=[
                Component(
                    id="alone", name="Alone", component_type=ComponentType.SERVICE
                ),
            ],
            edges=[],
            domain="cloud",
            confidence=1.0,
        )
        graph = builder.build(isolated_diagram)
        assert graph.nodes["alone"]["is_isolated"] is True

    def test_bidirectional_edge_adds_reverse(self, builder) -> None:
        diagram = DiagramGraph(
            components=[
                Component(id="a", name="A", component_type=ComponentType.SERVICE),
                Component(id="b", name="B", component_type=ComponentType.SERVICE),
            ],
            edges=[Edge(source_id="a", target_id="b", bidirectional=True)],
            domain="cloud",
            confidence=1.0,
        )
        graph = builder.build(diagram)
        assert graph.has_edge("a", "b")
        assert graph.has_edge("b", "a")


class TestAdjacencySummary:
    def test_structure(self, builder, diagram) -> None:
        graph = builder.build(diagram)
        summary = builder.get_adjacency_summary(graph)
        assert "gateway" in summary
        assert summary["gateway"]["name"] == "API Gateway"
        assert "sends_to" in summary["gateway"]
        assert "receives_from" in summary["gateway"]

    def test_gateway_sends_to_service(self, builder, diagram) -> None:
        graph = builder.build(diagram)
        summary = builder.get_adjacency_summary(graph)
        assert "Auth Service" in summary["gateway"]["sends_to"]

    def test_db_receives_from_service(self, builder, diagram) -> None:
        graph = builder.build(diagram)
        summary = builder.get_adjacency_summary(graph)
        assert "Auth Service" in summary["db"]["receives_from"]

    def test_duplicate_names_do_not_collide(self, builder) -> None:
        duplicate_diagram = DiagramGraph(
            components=[
                Component(
                    id="svc_a", name="Worker", component_type=ComponentType.SERVICE
                ),
                Component(
                    id="svc_b", name="Worker", component_type=ComponentType.SERVICE
                ),
            ],
            edges=[Edge(source_id="svc_a", target_id="svc_b")],
            domain="cloud",
            confidence=1.0,
        )
        graph = builder.build(duplicate_diagram)
        summary = builder.get_adjacency_summary(graph)
        assert set(summary.keys()) == {"svc_a", "svc_b"}


class TestCriticalNodes:
    def test_returns_list(self, builder, diagram) -> None:
        graph = builder.build(diagram)
        nodes = builder.get_critical_nodes(graph, top_n=2)
        assert isinstance(nodes, list)
        assert len(nodes) <= 2

    def test_top_n_respected(self, builder, diagram) -> None:
        graph = builder.build(diagram)
        nodes = builder.get_critical_nodes(graph, top_n=1)
        assert len(nodes) == 1


class TestMermaidExport:
    def test_starts_with_flowchart(self, builder, diagram) -> None:
        graph = builder.build(diagram)
        mermaid = builder.export_as_mermaid(graph)
        assert mermaid.startswith("flowchart LR")

    def test_contains_all_node_names(self, builder, diagram) -> None:
        graph = builder.build(diagram)
        mermaid = builder.export_as_mermaid(graph)
        assert "API Gateway" in mermaid
        assert "Auth Service" in mermaid
        assert "User DB" in mermaid

    def test_contains_arrows(self, builder, diagram) -> None:
        graph = builder.build(diagram)
        mermaid = builder.export_as_mermaid(graph)
        assert "-->" in mermaid
