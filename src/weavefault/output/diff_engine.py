"""
WeaveFault FMEADiffEngine — compare two FMEA snapshots and produce a diff report.

Identifies new, removed, and changed failure modes between two FMEADocument
versions. Produces a structured Markdown diff report for git-native review.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from weavefault.ingestion.schema import FMEADocument, FMEARow


def _row_key(row: FMEARow) -> str:
    """Stable key for matching rows across FMEA versions."""
    return f"{row.component_id}::{row.failure_mode.lower().strip()}"


@dataclass
class FMEADiff:
    """Result of comparing two FMEA document snapshots."""

    new_rows: list[FMEARow] = field(default_factory=list)
    removed_rows: list[FMEARow] = field(default_factory=list)
    changed_rows: list[tuple[FMEARow, FMEARow]] = field(default_factory=list)
    unchanged_count: int = 0
    generated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_changes(self) -> int:
        return len(self.new_rows) + len(self.removed_rows) + len(self.changed_rows)

    @property
    def has_changes(self) -> bool:
        return self.total_changes > 0


class FMEADiffEngine:
    """
    Compare two FMEADocument instances and produce a structured diff.

    Rows are matched by the composite key: component_id + failure_mode.
    A row is "changed" if any of its scored fields differ between versions.
    """

    SCORED_FIELDS = (
        "severity",
        "occurrence",
        "detection",
        "rpn",
        "recommended_action",
        "potential_effect",
    )

    def diff(self, before: FMEADocument, after: FMEADocument) -> FMEADiff:
        """
        Compare two FMEA documents and return a diff.

        Args:
            before: The earlier FMEA document.
            after: The later FMEA document.

        Returns:
            FMEADiff with new, removed, changed, and unchanged counts.
        """
        before_map = {_row_key(r): r for r in before.rows}
        after_map = {_row_key(r): r for r in after.rows}

        before_keys = set(before_map.keys())
        after_keys = set(after_map.keys())

        new_keys = after_keys - before_keys
        removed_keys = before_keys - after_keys
        common_keys = before_keys & after_keys

        new_rows = [after_map[k] for k in sorted(new_keys)]
        removed_rows = [before_map[k] for k in sorted(removed_keys)]

        changed_rows: list[tuple[FMEARow, FMEARow]] = []
        unchanged_count = 0

        for key in sorted(common_keys):
            old_row = before_map[key]
            new_row = after_map[key]
            if self._has_changed(old_row, new_row):
                changed_rows.append((old_row, new_row))
            else:
                unchanged_count += 1

        return FMEADiff(
            new_rows=new_rows,
            removed_rows=removed_rows,
            changed_rows=changed_rows,
            unchanged_count=unchanged_count,
        )

    def _has_changed(self, old: FMEARow, new: FMEARow) -> bool:
        """Return True if any scored field differs between two rows."""
        return any(
            getattr(old, field) != getattr(new, field) for field in self.SCORED_FIELDS
        )

    def to_markdown(self, diff: FMEADiff) -> str:
        """
        Render a FMEADiff as a Markdown report.

        Args:
            diff: The diff to render.

        Returns:
            Markdown string with summary + sections for new/removed/changed rows.
        """
        sections: list[str] = []

        # Header
        sections.append("# WeaveFault FMEA Diff Report")
        sections.append(
            f"*Generated: {diff.generated_at.strftime('%Y-%m-%d %H:%M UTC')}*"
        )

        # Summary
        sections.append("## Summary\n")
        sections.append(
            f"| Change Type | Count |\n"
            f"|-------------|-------|\n"
            f"| New failure modes | {len(diff.new_rows)} |\n"
            f"| Removed failure modes | {len(diff.removed_rows)} |\n"
            f"| Changed failure modes | {len(diff.changed_rows)} |\n"
            f"| Unchanged | {diff.unchanged_count} |"
        )

        if not diff.has_changes:
            sections.append("\n> No changes detected between the two FMEA snapshots.")
            return "\n\n".join(sections)

        # New rows
        if diff.new_rows:
            sections.append("## New Failure Modes\n")
            sections.append("| Component | Failure Mode | S | O | D | RPN | Action |")
            sections.append("|-----------|-------------|---|---|---|-----|--------|")
            for row in diff.new_rows:
                sections.append(
                    f"| ✅ {row.component_name} "
                    f"| {row.failure_mode} "
                    f"| {row.severity} "
                    f"| {row.occurrence} "
                    f"| {row.detection} "
                    f"| **{row.rpn}** "
                    f"| {row.recommended_action} |"
                )

        # Removed rows
        if diff.removed_rows:
            sections.append("## Removed Failure Modes\n")
            sections.append("| Component | Failure Mode | Previous RPN |")
            sections.append("|-----------|-------------|--------------|")
            for row in diff.removed_rows:
                sections.append(
                    f"| ❌ {row.component_name} "
                    f"| {row.failure_mode} "
                    f"| {row.rpn} |"
                )

        # Changed rows
        if diff.changed_rows:
            sections.append("## Changed Failure Modes\n")
            for old_row, new_row in diff.changed_rows:
                rpn_delta = new_row.rpn - old_row.rpn
                delta_str = f"+{rpn_delta}" if rpn_delta > 0 else str(rpn_delta)
                sections.append(
                    f"### {old_row.component_name} — {old_row.failure_mode}\n\n"
                    f"| Field | Before | After |\n"
                    f"|-------|--------|-------|\n"
                    f"| Severity | {old_row.severity} | {new_row.severity} |\n"
                    f"| Occurrence | {old_row.occurrence} | {new_row.occurrence} |\n"
                    f"| Detection | {old_row.detection} | {new_row.detection} |\n"
                    f"| RPN | {old_row.rpn} | **{new_row.rpn}** ({delta_str}) |\n"
                    f"| Action | {old_row.recommended_action} | {new_row.recommended_action} |"
                )

        sections.append(
            "---\n*Generated by WeaveFault — "
            "We weave through your architecture to find where it will fault.*"
        )

        return "\n\n".join(sections)
