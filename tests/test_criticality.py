"""
Tests for CriticalityAnalyzer — SPOF detection, scoring, risk tiers, annotation.
"""
from __future__ import annotations

import pytest

from weavefault.graph.builder import GraphBuilder
from weavefault.graph.criticality import TIER_THRESHOLDS, CriticalityAnalyzer
from weavefault.graph.propagation import CascadeSimulator
from weavefault.ingestion.schema import Component, ComponentType, DiagramGraph, Edge


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build(diagram: DiagramGraph):
    graph = GraphBuilder().build(diagram)
    cascades = CascadeSimulator().simulate_all(graph)
    return graph, cascades


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def analyzer() -> CriticalityAnalyzer:
    return CriticalityAnalyzer()


# ── Analyse ───────────────────────────────────────────────────────────────────


class TestAnalyze:
    def test_returns_dict_for_all_nodes(
        self, analyzer, three_node_graph, three_node_cascades
    ) -> None:
        result = analyzer.analyze(three_node_graph, three_node_cascades)
        assert set(result.keys()) == {"gateway", "service", "db"}

    def test_each_entry_has_required_keys(
        self, analyzer, three_node_graph, three_node_cascades
    ) -> None:
        result = analyzer.analyze(three_node_graph, three_node_cascades)
        required_keys = {
            "is_spof",
            "criticality_score",
            "risk_tier",
            "blast_radius_pct",
            "betweenness_centrality",
            "in_degree",
            "out_degree",
        }
        for data in result.values():
            assert required_keys.issubset(data.keys())

    def test_criticality_score_in_unit_interval(
        self, analyzer, cloud_graph, cloud_cascades
    ) -> None:
        result = analyzer.analyze(cloud_graph, cloud_cascades)
        for node_id, data in result.items():
            score = data["criticality_score"]
            assert 0.0 <= score <= 1.0, f"{node_id} score out of range: {score}"

    def test_risk_tier_is_valid_value(
        self, analyzer, cloud_graph, cloud_cascades
    ) -> None:
        result = analyzer.analyze(cloud_graph, cloud_cascades)
        valid_tiers = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        for data in result.values():
            assert data["risk_tier"] in valid_tiers

    def test_gateway_has_higher_score_than_leaf(
        self, analyzer, three_node_graph, three_node_cascades
    ) -> None:
        """API Gateway feeds the whole chain; DB is a leaf — gateway should score higher."""
        result = analyzer.analyze(three_node_graph, three_node_cascades)
        assert (
            result["gateway"]["criticality_score"] >= result["db"]["criticality_score"]
        )

    def test_empty_graph_returns_empty(self, analyzer) -> None:
        empty = DiagramGraph(components=[], edges=[], domain="cloud", confidence=1.0)
        graph = GraphBuilder().build(empty)
        cascades = CascadeSimulator().simulate_all(graph)
        result = analyzer.analyze(graph, cascades)
        assert result == {}


# ── SPOF detection ────────────────────────────────────────────────────────────


class TestGetSpofs:
    def test_hub_is_spof_in_star_topology(self, analyzer, star_graph) -> None:
        spofs = analyzer.get_spofs(star_graph)
        assert "hub" in spofs

    def test_spokes_are_not_spofs(self, analyzer, star_graph) -> None:
        spofs = analyzer.get_spofs(star_graph)
        for spoke in ("spoke_a", "spoke_b", "spoke_c"):
            assert spoke not in spofs

    def test_linear_middle_node_is_spof(self, analyzer, three_node_graph) -> None:
        """In a linear chain A→B→C, B is a SPOF."""
        spofs = analyzer.get_spofs(three_node_graph)
        assert "service" in spofs

    def test_leaf_node_is_not_spof(self, analyzer, three_node_graph) -> None:
        spofs = analyzer.get_spofs(three_node_graph)
        assert "db" not in spofs

    def test_empty_graph_no_spofs(self, analyzer) -> None:
        empty = DiagramGraph(components=[], edges=[], domain="cloud", confidence=1.0)
        graph = GraphBuilder().build(empty)
        assert analyzer.get_spofs(graph) == []

    def test_isolated_nodes_no_spofs(self, analyzer) -> None:
        diagram = DiagramGraph(
            components=[
                Component(id="a", name="A", component_type=ComponentType.SERVICE),
                Component(id="b", name="B", component_type=ComponentType.SERVICE),
            ],
            edges=[],
            domain="cloud",
            confidence=1.0,
        )
        graph = GraphBuilder().build(diagram)
        spofs = analyzer.get_spofs(graph)
        assert "a" not in spofs
        assert "b" not in spofs

    def test_spof_gets_score_bonus(self, analyzer, star_graph) -> None:
        """A SPOF node should receive a score bonus vs. a non-SPOF."""
        cascades = CascadeSimulator().simulate_all(star_graph)
        result = analyzer.analyze(star_graph, cascades)
        assert result["hub"]["is_spof"] is True
        assert result["spoke_a"]["is_spof"] is False
        assert (
            result["hub"]["criticality_score"] > result["spoke_a"]["criticality_score"]
        )


# ── Graph annotation ──────────────────────────────────────────────────────────


class TestAnnotateGraph:
    def test_annotate_sets_node_attributes(
        self, analyzer, three_node_graph, three_node_cascades
    ) -> None:
        analysis = analyzer.analyze(three_node_graph, three_node_cascades)
        analyzer.annotate_graph(three_node_graph, analysis)
        for node_id in three_node_graph.nodes:
            assert "criticality_score" in three_node_graph.nodes[node_id]
            assert "risk_tier" in three_node_graph.nodes[node_id]
            assert "is_spof" in three_node_graph.nodes[node_id]

    def test_annotate_returns_same_graph(
        self, analyzer, three_node_graph, three_node_cascades
    ) -> None:
        analysis = analyzer.analyze(three_node_graph, three_node_cascades)
        result = analyzer.annotate_graph(three_node_graph, analysis)
        assert result is three_node_graph

    def test_annotate_values_match_analysis(
        self, analyzer, three_node_graph, three_node_cascades
    ) -> None:
        analysis = analyzer.analyze(three_node_graph, three_node_cascades)
        analyzer.annotate_graph(three_node_graph, analysis)
        for node_id, data in analysis.items():
            node = three_node_graph.nodes[node_id]
            assert node["criticality_score"] == data["criticality_score"]
            assert node["risk_tier"] == data["risk_tier"]


# ── Tier thresholds ───────────────────────────────────────────────────────────


class TestTierThresholds:
    def test_critical_threshold_highest(self) -> None:
        assert TIER_THRESHOLDS["CRITICAL"] > TIER_THRESHOLDS["HIGH"]

    def test_high_above_medium(self) -> None:
        assert TIER_THRESHOLDS["HIGH"] > TIER_THRESHOLDS["MEDIUM"]

    def test_medium_positive(self) -> None:
        assert TIER_THRESHOLDS["MEDIUM"] > 0.0
