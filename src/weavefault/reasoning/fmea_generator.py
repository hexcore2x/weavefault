"""
WeaveFault FMEAGenerator - generate FMEA rows via graph-aware LLM prompts.

For each component in the diagram, builds a rich context prompt that includes:
  - Component metadata and type
  - Topology neighbours (sends_to / receives_from)
  - Cascade failure impact
  - Criticality analysis
  - RAG context (past FMEAs + standards)
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import networkx as nx

from weavefault.graph.propagation import CascadeChain
from weavefault.ingestion.schema import Component, DiagramGraph, FMEARow
from weavefault.standards import (
    StandardProfile,
    build_high_risk_rule,
    build_standard_metadata_guidance,
    build_standard_prompt_context,
    build_standard_score_guidance,
    canonical_standard_name,
    get_score_display_names,
    load_standard_profile,
)

logger = logging.getLogger(__name__)


class FMEAGenerator:
    """Generate FMEA rows for all components in a DiagramGraph."""

    def __init__(
        self,
        provider: str,
        model: str,
        rag_retriever: Any,
        api_key: str,
        config_dir: str | None = None,
    ) -> None:
        self.provider = provider.lower()
        self.model = model
        self.rag_retriever = rag_retriever
        self.api_key = api_key
        self.config_dir = config_dir

    def generate(
        self,
        diagram: DiagramGraph,
        graph: "nx.DiGraph",
        cascade_results: dict[str, CascadeChain],
        criticality: dict[str, dict],
        domain: str = "cloud",
        standard: str = "IEC_60812",
    ) -> list[FMEARow]:
        """
        Generate FMEA rows for all components in the diagram.

        Skips isolated external components with no edges.
        Returns all rows sorted by RPN descending.
        """
        from weavefault.graph.builder import GraphBuilder
        from weavefault.graph.propagation import CascadeSimulator

        standard_id = canonical_standard_name(standard)
        standard_profile = load_standard_profile(standard_id, self.config_dir)
        builder = GraphBuilder()
        adjacency = builder.get_adjacency_summary(graph)
        simulator = CascadeSimulator()
        all_rows: list[FMEARow] = []

        for component in diagram.components:
            if component.is_external:
                node_data = graph.nodes.get(component.id, {})
                if node_data.get("is_isolated", True):
                    logger.debug("Skipping isolated external: %s", component.name)
                    continue

            neighbours = adjacency.get(
                component.id,
                {"name": component.name, "sends_to": [], "receives_from": []},
            )
            cascade = cascade_results.get(component.id)
            criticality_info = criticality.get(
                component.id,
                {"risk_tier": "LOW", "is_spof": False, "criticality_score": 0.0},
            )

            if cascade:
                cascade_summary = simulator.format_cascade_for_prompt(cascade, graph)
            else:
                cascade_summary = f"No cascade data for {component.name}."

            rag_context = ""
            if self.rag_retriever is not None:
                try:
                    rag_context = self.rag_retriever.retrieve(
                        query=f"{component.name} {component.component_type.value} failure",
                        component_type=component.component_type.value,
                        domain=domain,
                    )
                except Exception as exc:
                    logger.debug("RAG retrieval failed: %s", exc)

            prompt = self._build_component_prompt(
                component=component,
                neighbours=neighbours,
                cascade_summary=cascade_summary,
                criticality_info=criticality_info,
                rag_context=rag_context or "No relevant examples found.",
                domain=domain,
                standard_profile=standard_profile,
            )

            try:
                response = self._call_llm(prompt)
                rows = self._parse_rows(response, component)
                all_rows.extend(rows)
                logger.info("Generated %d rows for %s", len(rows), component.name)
            except Exception as exc:
                logger.error("Failed to generate FMEA for %s: %s", component.name, exc)

        all_rows.sort(key=lambda row: row.rpn, reverse=True)
        logger.info("Total FMEA rows generated: %d", len(all_rows))
        return all_rows

    def _build_component_prompt(
        self,
        component: Component,
        neighbours: dict[str, Any],
        cascade_summary: str,
        criticality_info: dict[str, Any],
        rag_context: str,
        domain: str,
        standard_profile: StandardProfile,
    ) -> str:
        """Build the FMEA generation prompt for a single component."""
        metadata_example, metadata_guidance = build_standard_metadata_guidance(
            standard_profile
        )
        standard_context = build_standard_prompt_context(standard_profile)
        score_names = get_score_display_names(standard_profile)
        score_guide = build_standard_score_guidance(standard_profile)
        high_risk_rule = build_high_risk_rule(standard_profile)

        return f"""You are a senior reliability engineer performing FMEA for a {domain} system.

STANDARD CONTEXT:
{standard_context}

COMPONENT UNDER ANALYSIS:
Name: {component.name}
Type: {component.component_type.value}
Description: {component.description}
Risk tier: {criticality_info['risk_tier']}
Is SPOF: {criticality_info['is_spof']}

TOPOLOGY CONTEXT:
Sends data to: {neighbours.get('sends_to', [])}
Receives data from: {neighbours.get('receives_from', [])}

CASCADE IMPACT:
{cascade_summary}

RELEVANT PAST FMEA EXAMPLES:
{rag_context}

TASK:
Generate 3 to 5 distinct failure modes for this component.
Return ONLY valid JSON - no markdown, no preamble:

[
  {{
    "component_id": "{component.id}",
    "component_name": "{component.name}",
    "failure_mode": "specific failure mode",
    "potential_effect": "immediate effect on direct neighbours",
    "cascade_effects": ["downstream node 1", "downstream node 2"],
    "severity": 1,
    "occurrence": 1,
    "detection": 1,
    "recommended_action": "specific mitigation",
    "standard_clause": "relevant {standard_profile.id} clause",
    "standard_metadata": {metadata_example},
    "reasoning_chain": "why you assigned these scores",
    "confidence": 0.9
  }}
]

RPN scoring guide:
{score_names['severity']}: assign a 1-10 value in the `severity` field.
{score_names['occurrence']}: assign a 1-10 value in the `occurrence` field.
{score_names['detection']}: assign a 1-10 value in the `detection` field.
{score_guide}
{high_risk_rule}
{metadata_guidance}"""

    def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM provider with a text prompt."""
        if self.provider == "anthropic":
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)
            message = client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text

        if self.provider == "openai":
            import openai

            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content or ""

        raise ValueError(f"Unknown provider: {self.provider!r}")

    def _parse_rows(self, response: str, component: Component) -> list[FMEARow]:
        """
        Parse the LLM JSON response into a list of FMEARow objects.

        Strips markdown fences if present. Returns empty list on parse failure.
        """
        clean = response.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data: list[dict[str, Any]] | dict[str, Any] = json.loads(clean)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse FMEA rows for %s: %s", component.name, exc)
            return []

        if not isinstance(data, list):
            data = [data]

        rows: list[FMEARow] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                item["component_id"] = component.id
                item["component_name"] = component.name
                item["generated_by"] = self.model
                row = FMEARow(**item)
                rows.append(row)
            except Exception as exc:
                logger.warning("Skipping malformed FMEA row: %s", exc)

        return rows
