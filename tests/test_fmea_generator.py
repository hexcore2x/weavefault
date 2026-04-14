"""
Tests for FMEAGenerator._parse_rows and FMEARow/FMEADocument helpers.
"""

from __future__ import annotations

import json

import pytest
from weavefault.ingestion.schema import (
    Component,
    ComponentType,
    DiagramGraph,
    FMEADocument,
    FMEARow,
)
from weavefault.reasoning.fmea_generator import FMEAGenerator


@pytest.fixture
def generator() -> FMEAGenerator:
    return FMEAGenerator(
        provider="anthropic",
        model="claude-opus-4-6",
        rag_retriever=None,
        api_key="test-key",
    )


@pytest.fixture
def test_component() -> Component:
    return Component(
        id="auth_service",
        name="Auth Service",
        component_type=ComponentType.SERVICE,
        description="Handles authentication",
    )


def _make_valid_rows_json(component_id: str = "auth_service") -> str:
    rows = [
        {
            "component_id": component_id,
            "component_name": "Auth Service",
            "failure_mode": "JWT signing key rotation failure",
            "potential_effect": "All new sessions rejected",
            "cascade_effects": ["API Gateway", "Frontend"],
            "severity": 9,
            "occurrence": 3,
            "detection": 5,
            "recommended_action": "Implement key rotation monitoring",
            "standard_clause": "IEC 60812 Clause 7.4",
            "standard_metadata": {"asil": "ASIL_B"},
            "reasoning_chain": (
                "High severity because all auth blocked; "
                "low occurrence due to rare rotation events"
            ),
            "confidence": 0.88,
        },
        {
            "component_id": component_id,
            "component_name": "Auth Service",
            "failure_mode": "Database connection pool exhaustion",
            "potential_effect": "Auth requests timeout",
            "cascade_effects": ["User DB"],
            "severity": 7,
            "occurrence": 5,
            "detection": 4,
            "recommended_action": "Add connection pool monitoring and auto-scaling",
            "standard_clause": "IEC 60812 Clause 7.3",
            "reasoning_chain": "High occurrence in peak load; detectable via metrics",
            "confidence": 0.82,
        },
    ]
    return json.dumps(rows)


class TestParseRows:
    def test_valid_json_returns_fmea_rows(
        self, generator: FMEAGenerator, test_component: Component
    ) -> None:
        rows = generator._parse_rows(_make_valid_rows_json(), test_component)
        assert len(rows) == 2
        assert all(isinstance(row, FMEARow) for row in rows)

    def test_rpn_computed(
        self, generator: FMEAGenerator, test_component: Component
    ) -> None:
        rows = generator._parse_rows(_make_valid_rows_json(), test_component)
        for row in rows:
            assert row.rpn == row.severity * row.occurrence * row.detection

    def test_component_identity_overridden(
        self, generator: FMEAGenerator, test_component: Component
    ) -> None:
        rows = generator._parse_rows(_make_valid_rows_json("wrong_id"), test_component)
        for row in rows:
            assert row.component_id == "auth_service"
            assert row.component_name == "Auth Service"

    def test_generated_by_set(
        self, generator: FMEAGenerator, test_component: Component
    ) -> None:
        rows = generator._parse_rows(_make_valid_rows_json(), test_component)
        for row in rows:
            assert row.generated_by == "claude-opus-4-6"

    def test_standard_metadata_parsed(
        self, generator: FMEAGenerator, test_component: Component
    ) -> None:
        rows = generator._parse_rows(_make_valid_rows_json(), test_component)
        assert rows[0].standard_metadata == {"asil": "ASIL_B"}

    def test_invalid_json_returns_empty(
        self, generator: FMEAGenerator, test_component: Component
    ) -> None:
        rows = generator._parse_rows("not json", test_component)
        assert rows == []

    def test_markdown_fenced_json_stripped(
        self, generator: FMEAGenerator, test_component: Component
    ) -> None:
        fenced = f"```json\n{_make_valid_rows_json()}\n```"
        rows = generator._parse_rows(fenced, test_component)
        assert len(rows) == 2

    def test_single_dict_wrapped_in_list(
        self, generator: FMEAGenerator, test_component: Component
    ) -> None:
        single = json.dumps(
            {
                "component_id": "auth_service",
                "component_name": "Auth Service",
                "failure_mode": "crash",
                "potential_effect": "outage",
                "severity": 8,
                "occurrence": 2,
                "detection": 3,
                "recommended_action": "restart policy",
            }
        )
        rows = generator._parse_rows(single, test_component)
        assert len(rows) == 1


class TestFMEARowRPN:
    def test_rpn_is_product(self) -> None:
        row = FMEARow(
            component_id="x",
            component_name="X",
            failure_mode="crash",
            potential_effect="outage",
            severity=9,
            occurrence=5,
            detection=7,
        )
        assert row.rpn == 9 * 5 * 7

    def test_high_risk_threshold(self) -> None:
        row = FMEARow(
            component_id="x",
            component_name="X",
            failure_mode="crash",
            potential_effect="outage",
            severity=10,
            occurrence=5,
            detection=5,
        )
        assert row.rpn >= 200

    def test_low_risk(self) -> None:
        row = FMEARow(
            component_id="x",
            component_name="X",
            failure_mode="minor lag",
            potential_effect="slowness",
            severity=2,
            occurrence=2,
            detection=2,
        )
        assert row.rpn == 8
        assert row.rpn < 200

    def test_severity_out_of_range(self) -> None:
        with pytest.raises(Exception):
            FMEARow(
                component_id="x",
                component_name="X",
                failure_mode="crash",
                potential_effect="outage",
                severity=11,
                occurrence=5,
                detection=5,
            )


class TestFMEADocumentSave:
    def test_save_creates_file(self, tmp_path) -> None:
        diagram = DiagramGraph(
            components=[
                Component(id="svc", name="Svc", component_type=ComponentType.SERVICE)
            ],
            edges=[],
            domain="cloud",
            confidence=1.0,
        )
        row = FMEARow(
            component_id="svc",
            component_name="Svc",
            failure_mode="crash",
            potential_effect="outage",
            severity=5,
            occurrence=3,
            detection=4,
        )
        doc = FMEADocument(
            diagram_graph=diagram,
            rows=[row],
            domain="cloud",
            standard="IEC_60812",
        )
        doc.save(str(tmp_path))
        saved_files = list(tmp_path.glob("*.weavefault.json"))
        assert len(saved_files) == 1

    def test_high_risk_count_computed(self) -> None:
        diagram = DiagramGraph(
            components=[
                Component(id="svc", name="Svc", component_type=ComponentType.SERVICE)
            ],
            edges=[],
            domain="cloud",
            confidence=1.0,
        )
        rows = [
            FMEARow(
                component_id="svc",
                component_name="Svc",
                failure_mode=f"mode {i}",
                potential_effect="effect",
                severity=10,
                occurrence=5,
                detection=5,
            )
            for i in range(3)
        ]
        doc = FMEADocument(
            diagram_graph=diagram,
            rows=rows,
            domain="cloud",
            standard="IEC_60812",
        )
        assert doc.high_risk_count == 3

    def test_custom_high_risk_threshold_respected(self) -> None:
        diagram = DiagramGraph(
            components=[
                Component(id="svc", name="Svc", component_type=ComponentType.SERVICE)
            ],
            edges=[],
            domain="cloud",
            confidence=1.0,
        )
        rows = [
            FMEARow(
                component_id="svc",
                component_name="Svc",
                failure_mode="mode 1",
                potential_effect="effect",
                severity=5,
                occurrence=4,
                detection=6,
            ),
            FMEARow(
                component_id="svc",
                component_name="Svc",
                failure_mode="mode 2",
                potential_effect="effect",
                severity=4,
                occurrence=4,
                detection=4,
            ),
        ]
        doc = FMEADocument(
            diagram_graph=diagram,
            rows=rows,
            domain="cloud",
            standard="AIAG_FMEA4",
            high_risk_threshold=100,
        )
        assert doc.high_risk_count == 1

    def test_iso_high_risk_count_respects_asil_metadata(self) -> None:
        diagram = DiagramGraph(
            components=[
                Component(id="svc", name="Svc", component_type=ComponentType.SERVICE)
            ],
            edges=[],
            domain="embedded",
            confidence=1.0,
        )
        row = FMEARow(
            component_id="svc",
            component_name="Svc",
            failure_mode="unsafe state transition",
            potential_effect="driver loses braking support",
            severity=4,
            occurrence=2,
            detection=4,
            standard_metadata={"asil": "ASIL_D"},
        )
        doc = FMEADocument(
            diagram_graph=diagram,
            rows=[row],
            domain="embedded",
            standard="ISO_26262",
            high_risk_threshold=200,
        )
        assert row.rpn == 32
        assert doc.high_risk_count == 1
