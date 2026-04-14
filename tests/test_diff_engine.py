"""
Tests for FMEADiffEngine — diff computation and Markdown rendering.
"""

from __future__ import annotations

import pytest

from weavefault.ingestion.schema import (
    Component,
    ComponentType,
    DiagramGraph,
    FMEADocument,
    FMEARow,
)
from weavefault.output.diff_engine import FMEADiff, FMEADiffEngine, _row_key


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_doc(rows: list[FMEARow], domain: str = "cloud") -> FMEADocument:
    diagram = DiagramGraph(
        components=[
            Component(id="svc", name="Svc", component_type=ComponentType.SERVICE)
        ],
        edges=[],
        domain=domain,
        confidence=1.0,
    )
    return FMEADocument(
        diagram_graph=diagram,
        rows=rows,
        domain=domain,
        standard="IEC_60812",
    )


def _row(
    component_id: str = "svc",
    failure_mode: str = "crash",
    severity: int = 5,
    occurrence: int = 3,
    detection: int = 4,
    recommended_action: str = "restart",
    potential_effect: str = "outage",
) -> FMEARow:
    return FMEARow(
        component_id=component_id,
        component_name=component_id.replace("_", " ").title(),
        failure_mode=failure_mode,
        potential_effect=potential_effect,
        severity=severity,
        occurrence=occurrence,
        detection=detection,
        recommended_action=recommended_action,
    )


@pytest.fixture
def engine() -> FMEADiffEngine:
    return FMEADiffEngine()


# ── Row key ───────────────────────────────────────────────────────────────────


class TestRowKey:
    def test_combines_component_and_mode(self) -> None:
        row = _row("svc", "Crash Loop")
        key = _row_key(row)
        assert "svc" in key
        assert "crash loop" in key

    def test_case_insensitive_mode(self) -> None:
        r1 = _row("svc", "Crash Loop")
        r2 = _row("svc", "crash loop")
        assert _row_key(r1) == _row_key(r2)


# ── Diff computation ──────────────────────────────────────────────────────────


class TestDiff:
    def test_identical_documents_no_changes(self, engine) -> None:
        row = _row()
        before = _make_doc([row])
        after = _make_doc([row])
        diff = engine.diff(before, after)
        assert diff.total_changes == 0
        assert diff.unchanged_count == 1

    def test_new_row_detected(self, engine) -> None:
        before = _make_doc([_row("svc", "crash")])
        after = _make_doc([_row("svc", "crash"), _row("svc", "memory leak")])
        diff = engine.diff(before, after)
        assert len(diff.new_rows) == 1
        assert diff.new_rows[0].failure_mode == "memory leak"

    def test_removed_row_detected(self, engine) -> None:
        before = _make_doc([_row("svc", "crash"), _row("svc", "timeout")])
        after = _make_doc([_row("svc", "crash")])
        diff = engine.diff(before, after)
        assert len(diff.removed_rows) == 1
        assert diff.removed_rows[0].failure_mode == "timeout"

    def test_changed_severity_detected(self, engine) -> None:
        before = _make_doc([_row("svc", "crash", severity=5)])
        after = _make_doc([_row("svc", "crash", severity=9)])
        diff = engine.diff(before, after)
        assert len(diff.changed_rows) == 1
        old_row, new_row = diff.changed_rows[0]
        assert old_row.severity == 5
        assert new_row.severity == 9

    def test_changed_occurrence_detected(self, engine) -> None:
        before = _make_doc([_row("svc", "crash", occurrence=2)])
        after = _make_doc([_row("svc", "crash", occurrence=8)])
        diff = engine.diff(before, after)
        assert len(diff.changed_rows) == 1

    def test_changed_detection_detected(self, engine) -> None:
        before = _make_doc([_row("svc", "crash", detection=2)])
        after = _make_doc([_row("svc", "crash", detection=9)])
        diff = engine.diff(before, after)
        assert len(diff.changed_rows) == 1

    def test_changed_action_detected(self, engine) -> None:
        before = _make_doc([_row("svc", "crash", recommended_action="restart")])
        after = _make_doc(
            [_row("svc", "crash", recommended_action="blue-green deploy")]
        )
        diff = engine.diff(before, after)
        assert len(diff.changed_rows) == 1

    def test_empty_to_non_empty(self, engine) -> None:
        before = _make_doc([])
        after = _make_doc([_row("svc", "crash")])
        diff = engine.diff(before, after)
        assert len(diff.new_rows) == 1
        assert len(diff.removed_rows) == 0

    def test_non_empty_to_empty(self, engine) -> None:
        before = _make_doc([_row("svc", "crash")])
        after = _make_doc([])
        diff = engine.diff(before, after)
        assert len(diff.removed_rows) == 1
        assert len(diff.new_rows) == 0

    def test_has_changes_property(self, engine) -> None:
        before = _make_doc([_row("svc", "crash")])
        after = _make_doc([_row("svc", "timeout")])
        diff = engine.diff(before, after)
        assert diff.has_changes is True

    def test_no_changes_property(self, engine) -> None:
        row = _row()
        diff = engine.diff(_make_doc([row]), _make_doc([row]))
        assert diff.has_changes is False

    def test_total_changes_sums_correctly(self, engine) -> None:
        before = _make_doc([_row("svc", "crash"), _row("svc", "timeout")])
        after = _make_doc([_row("svc", "crash", severity=9), _row("svc", "leak")])
        diff = engine.diff(before, after)
        assert diff.total_changes == len(diff.new_rows) + len(diff.removed_rows) + len(
            diff.changed_rows
        )


# ── Markdown rendering ────────────────────────────────────────────────────────


class TestToMarkdown:
    def test_returns_string(self, engine) -> None:
        row = _row()
        diff = engine.diff(_make_doc([row]), _make_doc([row]))
        md = engine.to_markdown(diff)
        assert isinstance(md, str)
        assert len(md) > 0

    def test_contains_header(self, engine) -> None:
        diff = FMEADiff()
        md = engine.to_markdown(diff)
        assert "WeaveFault FMEA Diff Report" in md

    def test_no_changes_message(self, engine) -> None:
        row = _row()
        diff = engine.diff(_make_doc([row]), _make_doc([row]))
        md = engine.to_markdown(diff)
        assert "No changes detected" in md

    def test_new_rows_section_present(self, engine) -> None:
        before = _make_doc([])
        after = _make_doc([_row("svc", "crash")])
        diff = engine.diff(before, after)
        md = engine.to_markdown(diff)
        assert "New Failure Modes" in md
        assert "crash" in md

    def test_removed_rows_section_present(self, engine) -> None:
        before = _make_doc([_row("svc", "crash")])
        after = _make_doc([])
        diff = engine.diff(before, after)
        md = engine.to_markdown(diff)
        assert "Removed Failure Modes" in md

    def test_changed_rows_shows_delta(self, engine) -> None:
        before = _make_doc([_row("svc", "crash", severity=5)])
        after = _make_doc([_row("svc", "crash", severity=9)])
        diff = engine.diff(before, after)
        md = engine.to_markdown(diff)
        assert "Changed Failure Modes" in md
        assert "Severity" in md

    def test_rpn_delta_positive(self, engine) -> None:
        before = _make_doc(
            [_row("svc", "crash", severity=3, occurrence=3, detection=3)]
        )
        after = _make_doc([_row("svc", "crash", severity=8, occurrence=6, detection=7)])
        diff = engine.diff(before, after)
        md = engine.to_markdown(diff)
        assert "+" in md  # positive RPN delta indicator
