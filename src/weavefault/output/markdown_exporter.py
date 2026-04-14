"""
WeaveFault MarkdownExporter - export FMEA documents to Markdown.

Produces a clean .md file with:
- YAML front matter
- Summary table
- Full FMEA table
- Mermaid dependency graph
- High-risk section
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import networkx as nx

from weavefault.ingestion.schema import FMEADocument, FMEARow
from weavefault.standards import (
    build_high_risk_label,
    format_standard_metadata,
    get_score_short_labels,
    is_high_risk_row,
    load_standard_profile,
)

logger = logging.getLogger(__name__)


class MarkdownExporter:
    """Export FMEADocument to a git-friendly Markdown file."""

    def export(
        self,
        doc: FMEADocument,
        output_path: str,
        graph: "nx.DiGraph | None" = None,
    ) -> Path:
        """Export the FMEA document as a Markdown file."""
        dest = self._resolve_path(output_path, doc.id, ".md")
        dest.parent.mkdir(parents=True, exist_ok=True)

        content = self._render(doc, graph)
        dest.write_text(content, encoding="utf-8")
        logger.info("Markdown exported to %s", dest)
        return dest

    def _render(self, doc: FMEADocument, graph: "nx.DiGraph | None") -> str:
        profile = load_standard_profile(doc.standard)
        sections = [
            self._front_matter(doc),
            self._header(doc),
            self._summary_table(doc, profile),
            self._fmea_table(doc, profile),
        ]

        if graph is not None:
            sections.append(self._mermaid_graph(graph))

        high_risk = [
            row
            for row in doc.rows
            if is_high_risk_row(row, profile, threshold=doc.high_risk_threshold)
        ]
        if high_risk:
            sections.append(
                self._high_risk_section(high_risk, profile, doc.high_risk_threshold)
            )

        sections.append(self._footer(doc))
        return "\n\n".join(sections)

    def _front_matter(self, doc: FMEADocument) -> str:
        return (
            "---\n"
            f"weavefault_version: {doc.version}\n"
            f"document_id: {doc.id}\n"
            f"domain: {doc.domain}\n"
            f"standard: {doc.standard}\n"
            f"generated_at: {doc.generated_at.isoformat()}\n"
            f"model_used: {doc.model_used}\n"
            f"total_components: {doc.total_components}\n"
            f"high_risk_count: {doc.high_risk_count}\n"
            "---"
        )

    def _header(self, doc: FMEADocument) -> str:
        return (
            f"# WeaveFault FMEA - {doc.diagram_graph.source_file or doc.id}\n\n"
            f"> **Domain:** {doc.domain} | "
            f"**Standard:** {doc.standard} | "
            f"**Model:** {doc.model_used}"
        )

    def _summary_table(self, doc: FMEADocument, profile) -> str:
        high_risk_label = build_high_risk_label(profile, doc.high_risk_threshold)
        return (
            "## Summary\n\n"
            "| Metric | Value |\n"
            "|--------|-------|\n"
            f"| Total Components | {doc.total_components} |\n"
            f"| Failure Modes Generated | {len(doc.rows)} |\n"
            f"| High Risk ({high_risk_label}) | {doc.high_risk_count} |\n"
            f"| Generated At | {doc.generated_at.strftime('%Y-%m-%d %H:%M UTC')} |\n"
            f"| Source Diagram | `{doc.diagram_graph.source_file or 'N/A'}` |\n"
        )

    def _fmea_table(self, doc: FMEADocument, profile) -> str:
        if not doc.rows:
            return "## FMEA Rows\n\n*No rows generated.*"

        score_labels = get_score_short_labels(profile)
        lines = [
            "## FMEA Rows",
            "",
            (
                f"| Component | Failure Mode | Effect | {score_labels['severity']} "
                f"| {score_labels['occurrence']} | {score_labels['detection']} "
                "| RPN | Action |"
            ),
            "|-----------|-------------|--------|---|---|---|-----|--------|",
        ]
        for row in doc.rows:
            rpn_badge = (
                f"**{row.rpn}**"
                if is_high_risk_row(row, profile, threshold=doc.high_risk_threshold)
                else str(row.rpn)
            )
            lines.append(
                f"| {row.component_name} "
                f"| {row.failure_mode} "
                f"| {row.potential_effect} "
                f"| {row.severity} "
                f"| {row.occurrence} "
                f"| {row.detection} "
                f"| {rpn_badge} "
                f"| {row.recommended_action} |"
            )
        return "\n".join(lines)

    def _mermaid_graph(self, graph: "nx.DiGraph") -> str:
        from weavefault.graph.builder import GraphBuilder

        builder = GraphBuilder()
        mermaid = builder.export_as_mermaid(graph)
        return f"## Dependency Graph\n\n```mermaid\n{mermaid}\n```"

    def _high_risk_section(self, rows: list[FMEARow], profile, threshold: int) -> str:
        score_labels = get_score_short_labels(profile)
        high_risk_label = build_high_risk_label(profile, threshold)
        lines = [
            f"## High Risk Items ({high_risk_label})",
            "",
            "> These failure modes require immediate attention.",
            "",
        ]
        for row in sorted(rows, key=lambda item: item.rpn, reverse=True):
            lines.append(f"### {row.component_name} - {row.failure_mode}")
            lines.append(
                f"- **RPN:** {row.rpn} "
                f"({score_labels['severity']}={row.severity}, "
                f"{score_labels['occurrence']}={row.occurrence}, "
                f"{score_labels['detection']}={row.detection})"
            )
            lines.append(f"- **Effect:** {row.potential_effect}")
            if row.cascade_effects:
                lines.append(f"- **Cascade:** {', '.join(row.cascade_effects)}")
            if row.standard_metadata:
                lines.append(
                    f"- **Standard Context:** {format_standard_metadata(row.standard_metadata)}"
                )
            lines.append(f"- **Action:** {row.recommended_action}")
            if row.reasoning_chain:
                lines.append(f"- **Reasoning:** {row.reasoning_chain}")
            lines.append("")
        return "\n".join(lines)

    def _footer(self, doc: FMEADocument) -> str:
        return (
            "---\n\n"
            "*Generated by [WeaveFault](https://github.com/YOUR_USERNAME/weavefault) "
            "- We weave through your architecture to find where it will fault.*"
        )

    @staticmethod
    def _resolve_path(output_path: str, doc_id: str, suffix: str) -> Path:
        dest = Path(output_path)
        if dest.is_dir():
            return dest / f"fmea_{doc_id}{suffix}"
        if not dest.suffix:
            return dest.with_suffix(suffix)
        return dest
