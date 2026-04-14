"""
Tests for CascadeSimulator — BFS propagation, blast radius, worst failures.
"""

from __future__ import annotations

import pytest

from weavefault.graph.builder import GraphBuilder
from weavefault.graph.propagation import CascadeChain, CascadeSimulator
from weavefault.ingestion.schema import Component, ComponentType, DiagramGraph, Edge


def _make_chain_diagram() -> DiagramGraph:
    """A → B → C → D (linear chain)."""
    return DiagramGraph(
        components=[
            Component(id="a", name="A", component_type=ComponentType.SERVICE),
            Component(id="b", name="B", component_type=ComponentType.SERVICE),
            Component(id="c", name="C", component_type=ComponentType.SERVICE),
            Component(id="d", name="D", component_type=ComponentType.DATABASE),
        ],
        edges=[
            Edge(source_id="a", target_id="b"),
            Edge(source_id="b", target_id="c"),
            Edge(source_id="c", target_id="d"),
        ],
        domain="cloud",
        confidence=1.0,
    )


@pytest.fixture
def simulator() -> CascadeSimulator:
    return CascadeSimulator()


@pytest.fixture
def chain_graph():
    diagram = _make_chain_diagram()
    return GraphBuilder().build(diagram)


class TestSimulate:
    def test_returns_cascade_chain(self, simulator, chain_graph) -> None:
        result = simulator.simulate(chain_graph, "a")
        assert isinstance(result, CascadeChain)

    def test_origin_id_set(self, simulator, chain_graph) -> None:
        result = simulator.simulate(chain_graph, "a")
        assert result.origin_id == "a"

    def test_origin_name_resolved(self, simulator, chain_graph) -> None:
        result = simulator.simulate(chain_graph, "a")
        assert result.origin_name == "A"

    def test_full_chain_propagation(self, simulator, chain_graph) -> None:
        result = simulator.simulate(chain_graph, "a")
        assert set(result.affected_nodes) == {"b", "c", "d"}

    def test_leaf_node_has_no_affected(self, simulator, chain_graph) -> None:
        result = simulator.simulate(chain_graph, "d")
        assert result.affected_nodes == []
        assert result.blast_radius_pct == pytest.approx(0.0)

    def test_blast_radius_correct(self, simulator, chain_graph) -> None:
        # "a" failing affects b, c, d = 3 of 4 nodes = 75%
        result = simulator.simulate(chain_graph, "a")
        assert result.blast_radius_pct == pytest.approx(75.0)

    def test_max_depth_computed(self, simulator, chain_graph) -> None:
        result = simulator.simulate(chain_graph, "a")
        assert result.max_depth == 3

    def test_nonexistent_node_returns_empty_chain(self, simulator, chain_graph) -> None:
        result = simulator.simulate(chain_graph, "nonexistent")
        assert result.affected_nodes == []


class TestSimulateAll:
    def test_returns_dict_for_all_nodes(self, simulator, chain_graph) -> None:
        results = simulator.simulate_all(chain_graph)
        assert set(results.keys()) == {"a", "b", "c", "d"}

    def test_each_value_is_cascade_chain(self, simulator, chain_graph) -> None:
        results = simulator.simulate_all(chain_graph)
        for chain in results.values():
            assert isinstance(chain, CascadeChain)


class TestGetWorstFailures:
    def test_sorted_by_blast_radius(self, simulator, chain_graph) -> None:
        results = simulator.simulate_all(chain_graph)
        worst = simulator.get_worst_failures(results, top_n=3)
        radii = [c.blast_radius_pct for c in worst]
        assert radii == sorted(radii, reverse=True)

    def test_top_n_respected(self, simulator, chain_graph) -> None:
        results = simulator.simulate_all(chain_graph)
        worst = simulator.get_worst_failures(results, top_n=2)
        assert len(worst) == 2


class TestFormatCascadeForPrompt:
    def test_returns_string(self, simulator, chain_graph) -> None:
        results = simulator.simulate_all(chain_graph)
        chain = results["a"]
        text = simulator.format_cascade_for_prompt(chain, chain_graph)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_contains_origin_name(self, simulator, chain_graph) -> None:
        results = simulator.simulate_all(chain_graph)
        text = simulator.format_cascade_for_prompt(results["a"], chain_graph)
        assert "A" in text

    def test_empty_chain_message(self, simulator, chain_graph) -> None:
        results = simulator.simulate_all(chain_graph)
        text = simulator.format_cascade_for_prompt(results["d"], chain_graph)
        assert "no downstream" in text.lower()
