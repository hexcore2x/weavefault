"""
Tests for RPNScorer review logic and prompt generation.
"""

from __future__ import annotations

import json

import pytest

from weavefault.ingestion.schema import FMEARow
from weavefault.reasoning.rpn_scorer import RPNScorer


@pytest.fixture
def sample_row() -> FMEARow:
    return FMEARow(
        component_id="brake_ecu",
        component_name="Brake ECU",
        failure_mode="unsafe torque command",
        potential_effect="loss of braking support",
        cascade_effects=["Brake Actuator"],
        severity=4,
        occurrence=2,
        detection=4,
        standard_metadata={"asil": "ASIL_B"},
        reasoning_chain="Initial estimate",
    )


class TestRPNScorer:
    def test_score_all_returns_empty_list_when_no_rows(self) -> None:
        scorer = RPNScorer(
            provider="custom",
            model="test-model",
            api_key="test-key",
        )
        assert scorer.score_all([]) == []

    def test_build_review_prompt_uses_standard_specific_labels(
        self, sample_row: FMEARow
    ) -> None:
        scorer = RPNScorer(
            provider="custom",
            model="test-model",
            api_key="test-key",
            standard="ISO_26262",
            domain="embedded",
        )

        prompt = scorer._build_review_prompt(sample_row)

        assert "Exposure" in prompt
        assert "Controllability" in prompt
        assert "ASIL C/D or RPN >= 200" in prompt
        assert "embedded" in prompt

    def test_review_row_updates_scores_from_fenced_json(
        self, sample_row: FMEARow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scorer = RPNScorer(
            provider="custom",
            model="test-model",
            api_key="test-key",
            standard="ISO_26262",
        )
        payload = {
            "severity": 7,
            "occurrence": 3,
            "detection": 5,
            "reasoning_chain": "Adjusted after reviewing cascade impact",
            "standard_metadata": {"asil": "ASIL_C"},
        }
        monkeypatch.setattr(
            scorer,
            "_call_llm",
            lambda prompt: f"```json\n{json.dumps(payload)}\n```",
        )

        reviewed = scorer._review_row(sample_row)

        assert reviewed.severity == 7
        assert reviewed.occurrence == 3
        assert reviewed.detection == 5
        assert reviewed.rpn == 7 * 3 * 5
        assert reviewed.standard_metadata == {"asil": "ASIL_C"}
        assert reviewed.reasoning_chain == "Adjusted after reviewing cascade impact"

    def test_review_row_returns_original_row_on_invalid_json(
        self, sample_row: FMEARow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scorer = RPNScorer(
            provider="custom",
            model="test-model",
            api_key="test-key",
        )
        monkeypatch.setattr(scorer, "_call_llm", lambda prompt: "not-json")

        reviewed = scorer._review_row(sample_row)

        assert reviewed is sample_row

    def test_score_all_falls_back_to_original_row_when_review_raises(
        self, sample_row: FMEARow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scorer = RPNScorer(
            provider="custom",
            model="test-model",
            api_key="test-key",
        )

        def boom(row: FMEARow) -> FMEARow:
            raise RuntimeError("llm unavailable")

        monkeypatch.setattr(scorer, "_review_row", boom)

        reviewed = scorer.score_all([sample_row])

        assert reviewed == [sample_row]

    def test_call_llm_raises_for_unknown_provider(self, sample_row: FMEARow) -> None:
        scorer = RPNScorer(
            provider="custom",
            model="test-model",
            api_key="test-key",
        )

        with pytest.raises(ValueError, match="Unknown provider"):
            scorer._call_llm("prompt")
