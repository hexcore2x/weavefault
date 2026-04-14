"""
WeaveFault GraphBuilder - build an annotated NetworkX DiGraph from a DiagramGraph.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import networkx as nx

from weavefault.ingestion.schema import DiagramGraph

logger = logging.getLogger(__name__)


class GraphBuilder:
    """
    Build and annotate a NetworkX DiGraph from a parsed DiagramGraph.

    All component attributes are stored as node attributes.
    Centrality metrics are computed and stored per node.
    """

    def build(self, diagram: DiagramGraph) -> "nx.DiGraph":
        """
        Build an annotated directed graph from a DiagramGraph.

        Args:
            diagram: Parsed diagram with components and edges.

        Returns:
            Annotated nx.DiGraph with centrality metrics as node attributes.
        """
        import networkx as nx

        graph = nx.DiGraph()

        for component in diagram.components:
            graph.add_node(
                component.id,
                name=component.name,
                component_type=component.component_type.value,
                description=component.description,
                is_external=component.is_external,
                is_critical=component.is_critical,
                metadata=component.metadata,
                x=component.x,
                y=component.y,
            )

        for edge in diagram.edges:
            if edge.source_id not in graph.nodes or edge.target_id not in graph.nodes:
                logger.warning(
                    "Skipping edge %s->%s: endpoint not found",
                    edge.source_id,
                    edge.target_id,
                )
                continue
            graph.add_edge(
                edge.source_id,
                edge.target_id,
                label=edge.label,
                protocol=edge.protocol,
                data_flow=edge.data_flow,
                bidirectional=edge.bidirectional,
            )
            if edge.bidirectional:
                graph.add_edge(
                    edge.target_id,
                    edge.source_id,
                    label=edge.label,
                    protocol=edge.protocol,
                    data_flow=edge.data_flow,
                    bidirectional=True,
                )

        if graph.number_of_nodes() > 0:
            betweenness = nx.betweenness_centrality(graph, normalized=True)
            for node_id in graph.nodes:
                in_degree = graph.in_degree(node_id)
                out_degree = graph.out_degree(node_id)
                graph.nodes[node_id]["in_degree"] = in_degree
                graph.nodes[node_id]["out_degree"] = out_degree
                graph.nodes[node_id]["betweenness_centrality"] = betweenness.get(
                    node_id, 0.0
                )
                graph.nodes[node_id]["is_isolated"] = (in_degree + out_degree) == 0

        logger.info(
            "Built graph: %d nodes, %d edges",
            graph.number_of_nodes(),
            graph.number_of_edges(),
        )
        return graph

    def get_adjacency_summary(self, graph: "nx.DiGraph") -> dict[str, dict]:
        """
        Return a human-readable adjacency summary for every node keyed by node ID.

        Returns:
            Dict mapping node_id to adjacency information.
        """
        summary: dict[str, dict] = {}
        for node_id in graph.nodes:
            name = graph.nodes[node_id].get("name", node_id)
            successor_ids = list(graph.successors(node_id))
            predecessor_ids = list(graph.predecessors(node_id))
            sends_to = [graph.nodes[nb].get("name", nb) for nb in successor_ids]
            receives_from = [graph.nodes[nb].get("name", nb) for nb in predecessor_ids]
            summary[node_id] = {
                "name": name,
                "sends_to": sends_to,
                "receives_from": receives_from,
                "sends_to_ids": successor_ids,
                "receives_from_ids": predecessor_ids,
            }
        return summary

    def get_critical_nodes(self, graph: "nx.DiGraph", top_n: int = 5) -> list[str]:
        """
        Return the top_n node IDs ranked by betweenness centrality (descending).
        """
        scored = [
            (node_id, graph.nodes[node_id].get("betweenness_centrality", 0.0))
            for node_id in graph.nodes
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return [node_id for node_id, _ in scored[:top_n]]

    def export_as_mermaid(self, graph: "nx.DiGraph") -> str:
        """
        Export the graph as a Mermaid flowchart diagram string.

        Returns:
            Mermaid LR flowchart syntax.
        """
        lines = ["flowchart LR"]

        for node_id in graph.nodes:
            name = graph.nodes[node_id].get("name", node_id)
            component_type = graph.nodes[node_id].get("component_type", "UNKNOWN")
            safe_id = node_id.replace("-", "_")
            lines.append(f'    {safe_id}["{name}\\n[{component_type}]"]')

        for source, target, data in graph.edges(data=True):
            safe_source = source.replace("-", "_")
            safe_target = target.replace("-", "_")
            label = data.get("label", "")
            if label:
                lines.append(f"    {safe_source} -->|{label}| {safe_target}")
            else:
                lines.append(f"    {safe_source} --> {safe_target}")

        return "\n".join(lines)
