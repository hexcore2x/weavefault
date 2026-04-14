"""
WeaveFault CriticalityAnalyzer - identify SPOFs, critical paths, and risk tiers.

Combines graph topology metrics with cascade blast radius to assign
per-node criticality scores and risk classifications.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import networkx as nx

from weavefault.graph.propagation import CascadeChain

logger = logging.getLogger(__name__)

TIER_THRESHOLDS = {
    "CRITICAL": 0.7,
    "HIGH": 0.45,
    "MEDIUM": 0.2,
}


class CriticalityAnalyzer:
    """
    Compute per-node criticality from topology metrics and cascade results.

    Assigns each node a criticality_score (0-1), risk_tier, and SPOF flag.
    """

    def analyze(
        self,
        graph: "nx.DiGraph",
        cascade_results: dict[str, CascadeChain],
    ) -> dict[str, dict]:
        """
        Compute criticality for every node in the graph.

        Criticality score = weighted combination of:
          - betweenness_centrality (topology influence)
          - blast_radius_pct / 100 (cascade reach)
          - out_degree / max_out_degree (how many downstream depend on this node)
        """
        import networkx as nx

        spofs = set(self.get_spofs(graph))
        out_degrees = [graph.out_degree(node_id) for node_id in graph.nodes]
        max_out = max(out_degrees, default=1) or 1

        results: dict[str, dict] = {}
        for node_id in graph.nodes:
            node_data = graph.nodes[node_id]
            betweenness = node_data.get("betweenness_centrality", 0.0)
            in_degree = node_data.get("in_degree", graph.in_degree(node_id))
            out_degree = node_data.get("out_degree", graph.out_degree(node_id))
            cascade = cascade_results.get(node_id)
            blast = cascade.blast_radius_pct / 100.0 if cascade else 0.0

            score = 0.40 * betweenness + 0.40 * blast + 0.20 * (out_degree / max_out)
            score = min(1.0, score)

            is_spof = node_id in spofs
            if is_spof:
                score = min(1.0, score + 0.15)

            if score >= TIER_THRESHOLDS["CRITICAL"]:
                tier = "CRITICAL"
            elif score >= TIER_THRESHOLDS["HIGH"]:
                tier = "HIGH"
            elif score >= TIER_THRESHOLDS["MEDIUM"]:
                tier = "MEDIUM"
            else:
                tier = "LOW"

            results[node_id] = {
                "is_spof": is_spof,
                "criticality_score": round(score, 4),
                "risk_tier": tier,
                "blast_radius_pct": cascade.blast_radius_pct if cascade else 0.0,
                "betweenness_centrality": betweenness,
                "in_degree": in_degree,
                "out_degree": out_degree,
            }

        return results

    def get_spofs(self, graph: "nx.DiGraph") -> list[str]:
        """
        Identify single points of failure (SPOFs).

        A node is a SPOF if removing it increases the number of weakly
        connected components in the graph.
        """
        import networkx as nx

        if graph.number_of_nodes() == 0:
            return []

        base_components = nx.number_weakly_connected_components(graph)

        spofs: list[str] = []
        for node_id in list(graph.nodes):
            test_graph = graph.copy()
            test_graph.remove_node(node_id)
            new_components = nx.number_weakly_connected_components(test_graph)
            if new_components > base_components:
                spofs.append(node_id)

        logger.info("Found %d SPOFs", len(spofs))
        return spofs

    def annotate_graph(
        self,
        graph: "nx.DiGraph",
        analysis: dict[str, dict],
    ) -> "nx.DiGraph":
        """Write criticality analysis results as node attributes on the graph."""
        for node_id, data in analysis.items():
            if node_id in graph.nodes:
                graph.nodes[node_id]["criticality_score"] = data["criticality_score"]
                graph.nodes[node_id]["risk_tier"] = data["risk_tier"]
                graph.nodes[node_id]["is_spof"] = data["is_spof"]
        return graph
