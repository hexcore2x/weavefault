"""
Tests for standard-specific configuration helpers.
"""
from __future__ import annotations

from weavefault.standards import (
    build_high_risk_label,
    build_standard_metadata_guidance,
    build_standard_score_guidance,
    canonical_standard_name,
    count_high_risk_rows,
    get_score_header_labels,
    is_high_risk_row,
    load_standard_profile,
)


class TestCanonicalStandardName:
    def test_aiag_alias_maps_to_canonical_id(self) -> None:
        assert canonical_standard_name("AIAG") == "AIAG_FMEA4"


class TestLoadStandardProfile:
    def test_aiag_threshold_loaded(self) -> None:
        profile = load_standard_profile("AIAG_FMEA4")
        assert profile.high_risk_threshold == 100

    def test_iso_profile_exposes_asil_levels(self) -> None:
        profile = load_standard_profile("ISO_26262")
        assert "ASIL_D" in profile.asil_levels

    def test_iso_headers_use_sec_labels(self) -> None:
        profile = load_standard_profile("ISO_26262")
        headers = get_score_header_labels(profile)
        assert headers["occurrence"] == "Exposure (E)"
        assert headers["detection"] == "Controllability (C)"


class TestStandardMetadataGuidance:
    def test_iso_guidance_requests_asil(self) -> None:
        example, instruction = build_standard_metadata_guidance(
            load_standard_profile("ISO_26262")
        )
        assert '"asil"' in example
        assert "ASIL" in instruction

    def test_mil_guidance_requests_probability_level(self) -> None:
        example, instruction = build_standard_metadata_guidance(
            load_standard_profile("MIL_STD_1629")
        )
        assert '"probability_level"' in example
        assert "probability_level" in instruction


class TestRiskSemantics:
    def test_iso_high_risk_label_mentions_asil(self) -> None:
        label = build_high_risk_label(load_standard_profile("ISO_26262"))
        assert "ASIL C/D" in label

    def test_iso_asil_d_is_high_risk_even_below_threshold(self) -> None:
        row = {
            "rpn": 40,
            "standard_metadata": {"asil": "ASIL_D"},
        }
        assert is_high_risk_row(row, "ISO_26262", threshold=200)

    def test_mil_category_ii_counts_as_high_risk(self) -> None:
        rows = [
            {
                "rpn": 60,
                "standard_metadata": {"criticality_category": "Category_II"},
            }
        ]
        assert count_high_risk_rows(rows, "MIL_STD_1629", threshold=200) == 1

    def test_iso_score_guidance_mentions_sec_mapping(self) -> None:
        guidance = build_standard_score_guidance(load_standard_profile("ISO_26262"))
        assert "S/E/C" in guidance
