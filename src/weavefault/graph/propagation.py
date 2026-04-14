"""
WeaveFault CascadeSimulator — BFS failure propagation through a directed graph.

Simulates "if component X fails, what else breaks?" by following directed
edges from the origin node and computing blast radius.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import networkx as nx

logger = logging.getLogger(__name__)


@dataclass
class CascadeChain:
    """Result of a cascade failure simulation from a single origin node."""

    origin_id: str
    origin_name: str
    affected_nodes: list[str] = field(default_factory=list)
    paths: list[list[str]] = field(default_factory=list)
    max_depth: int = 0
    blast_radius_pct: float = 0.0


class CascadeSimulator:
    """
    Simulate failure propagation through a directed dependency graph.

    Uses BFS to find all nodes reachable from a failed origin node,
    then computes blast radius as a fraction of total graph size.
    """

    def simulate(self, graph: "nx.DiGraph", failed_node_id: str) -> CascadeChain:
        """
        Simulate a failure originating at failed_node_id.

        Follows directed edges outward from the origin (i.e., "who depends on
        this node?" = successors in the dependency graph).

        Args:
            graph: The annotated dependency graph.
            failed_node_id: Node ID of the component that fails.

        Returns:
            CascadeChain describing all affected nodes and propagation paths.
        """
        if failed_node_id not in graph.nodes:
            logger.warning(
                "Node %r not in graph — returning empty chain", failed_node_id
            )
            return CascadeChain(
                origin_id=failed_node_id,
                origin_name=failed_node_id,
            )

        origin_name = graph.nodes[failed_node_id].get("name", failed_node_id)
        total_nodes = graph.number_of_nodes()

        # BFS — track visited nodes and the paths that led to them
        visited: set[str] = set()
        paths: list[list[str]] = []
        max_depth = 0

        queue: deque[tuple[str, list[str]]] = deque()
        queue.append((failed_node_id, [failed_node_id]))

        while queue:
            current, path = queue.popleft()
            depth = len(path) - 1
            max_depth = max(max_depth, depth)

            for neighbour in graph.successors(current):
                if neighbour == failed_node_id or neighbour in visited:
                    continue
                visited.add(neighbour)
                new_path = path + [neighbour]
                paths.append(new_path)
                queue.append((neighbour, new_path))

        affected_nodes = list(visited)
        blast_radius_pct = (
            len(affected_nodes) / total_nodes * 100.0 if total_nodes > 0 else 0.0
        )

        return CascadeChain(
            origin_id=failed_node_id,
            origin_name=origin_name,
            affected_nodes=affected_nodes,
            paths=paths,
            max_depth=max_depth,
            blast_radius_pct=blast_radius_pct,
        )

    def simulate_all(self, graph: "nx.DiGraph") -> dict[str, CascadeChain]:
        """
        Run cascade simulation for every node in the graph.

        Args:
            graph: The annotated dependency graph.

        Returns:
            Dict mapping node_id → CascadeChain.
        """
        results: dict[str, CascadeChain] = {}
        for node_id in graph.nodes:
            results[node_id] = self.simulate(graph, node_id)
        logger.info("Simulated cascades for %d nodes", len(results))
        return results

    def get_worst_failures(
        self, results: dict[str, CascadeChain], top_n: int = 5
    ) -> list[CascadeChain]:
        """
        Return the top_n cascades sorted by blast_radius_pct descending.

        Args:
            results: Output of simulate_all().
            top_n: Number of top cascades to return.

        Returns:
            Sorted list of CascadeChain objects.
        """
        chains = list(results.values())
        chains.sort(key=lambda c: c.blast_radius_pct, reverse=True)
        return chains[:top_n]

    def format_cascade_for_prompt(
        self, chain: CascadeChain, graph: "nx.DiGraph"
    ) -> str:
        """
        Format a CascadeChain as a human-readable string for use in LLM prompts.

        Args:
            chain: The cascade chain to format.
            graph: The source graph (used to resolve node names).

        Returns:
            A concise English description of the cascade impact.
        """
        if not chain.affected_nodes:
            return f"If {chain.origin_name} fails: no downstream components affected."

        def node_name(nid: str) -> str:
            return (
                graph.nodes.get(nid, {}).get("name", nid) if nid in graph.nodes else nid
            )

        # Split direct vs indirect (depth 1 vs deeper)
        direct: list[str] = []
        indirect: list[str] = []
        for path in chain.paths:
            if len(path) == 2:  # [origin, affected]
                direct.append(node_name(path[1]))
            elif len(path) > 2:
                indirect.append(node_name(path[-1]))

        direct_str = ", ".join(sorted(set(direct))) or "none"
        indirect_str = ", ".join(sorted(set(indirect))) or "none"

        return (
            f"If {chain.origin_name} fails: directly affects [{direct_str}], "
            f"then propagates to [{indirect_str}] "
            f"(blast radius: {chain.blast_radius_pct:.0f}%, "
            f"max depth: {chain.max_depth})"
        )
