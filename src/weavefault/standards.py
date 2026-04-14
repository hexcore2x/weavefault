"""
WeaveFault standard utilities.

Loads standard-specific scoring guidance and thresholds so generation,
scoring, and export paths stay aligned with the selected methodology.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
_STANDARD_ALIASES = {"AIAG": "AIAG_FMEA4"}
_FALLBACK_THRESHOLDS = {
    "IEC_60812": {"high": 200, "medium": 100},
    "AIAG_FMEA4": {"high": 100, "medium": 50},
    "MIL_STD_1629": {"high": 200, "medium": 100},
    "ISO_26262": {"high": 200, "medium": 100},
}
_FALLBACK_NOTES = {
    "IEC_60812": "Default standard for cloud and general industrial systems.",
    "AIAG_FMEA4": "Primary standard for automotive and mechanical manufacturing FMEA.",
    "MIL_STD_1629": "Defense and aerospace standard. Uses criticality analysis alongside RPN.",
    "ISO_26262": "Functional safety standard for automotive. ASIL rating supplements RPN.",
}
_SCORE_DISPLAY_NAMES = {
    "IEC_60812": {
        "severity": "Severity",
        "occurrence": "Occurrence",
        "detection": "Detection",
    },
    "AIAG_FMEA4": {
        "severity": "Severity",
        "occurrence": "Occurrence",
        "detection": "Detection",
    },
    "MIL_STD_1629": {
        "severity": "Severity",
        "occurrence": "Probability",
        "detection": "Detection",
    },
    "ISO_26262": {
        "severity": "Severity",
        "occurrence": "Exposure",
        "detection": "Controllability",
    },
}
_SCORE_SHORT_LABELS = {
    "IEC_60812": {"severity": "S", "occurrence": "O", "detection": "D"},
    "AIAG_FMEA4": {"severity": "S", "occurrence": "O", "detection": "D"},
    "MIL_STD_1629": {"severity": "S", "occurrence": "P", "detection": "D"},
    "ISO_26262": {"severity": "S", "occurrence": "E", "detection": "C"},
}
_HIGH_RISK_METADATA_RULES = {
    "IEC_60812": {},
    "AIAG_FMEA4": {},
    "MIL_STD_1629": {"criticality_category": {"Category_I", "Category_II"}},
    "ISO_26262": {"asil": {"ASIL_C", "ASIL_D"}},
}


@dataclass(frozen=True)
class StandardProfile:
    """Resolved configuration for one supported FMEA standard."""

    id: str
    full_name: str
    high_risk_threshold: int
    medium_risk_threshold: int
    notes: str = ""
    scales: dict[str, Any] = field(default_factory=dict)
    criticality_categories: dict[str, str] = field(default_factory=dict)
    asil_levels: dict[str, str] = field(default_factory=dict)
    asil_determination: dict[str, Any] = field(default_factory=dict)


def canonical_standard_name(standard: str) -> str:
    """Resolve aliases to the canonical standard ID used throughout the app."""
    return _STANDARD_ALIASES.get(standard, standard)


def load_standard_profile(
    standard: str,
    config_dir: str | Path | None = None,
) -> StandardProfile:
    """Load a standard profile from config, falling back to built-in defaults."""
    standard_id = canonical_standard_name(standard)
    raw = _load_config(config_dir).get(standard_id, {})
    thresholds = raw.get("rpn_thresholds", {})
    fallback = _FALLBACK_THRESHOLDS.get(standard_id, _FALLBACK_THRESHOLDS["IEC_60812"])

    return StandardProfile(
        id=standard_id,
        full_name=raw.get("full_name", standard_id.replace("_", " ")),
        high_risk_threshold=int(thresholds.get("high", fallback["high"])),
        medium_risk_threshold=int(thresholds.get("medium", fallback["medium"])),
        notes=raw.get("notes", _FALLBACK_NOTES.get(standard_id, "")),
        scales=raw.get("scales", {}),
        criticality_categories=raw.get("criticality_categories", {}),
        asil_levels=raw.get("asil_levels", {}),
        asil_determination=raw.get("asil_determination", {}),
    )


def build_standard_prompt_context(profile: StandardProfile) -> str:
    """Render a concise prompt block describing the selected standard."""
    parts = [
        f"Apply {profile.full_name}.",
        build_high_risk_rule(profile),
    ]
    if profile.notes:
        parts.append(f"Notes: {profile.notes}")

    if profile.criticality_categories:
        cats = "; ".join(
            f"{key}={value}" for key, value in profile.criticality_categories.items()
        )
        parts.append(f"Criticality categories: {cats}")

    if profile.asil_levels:
        asil = "; ".join(f"{key}={value}" for key, value in profile.asil_levels.items())
        parts.append(f"ASIL levels: {asil}")

    return "\n".join(parts)


def build_standard_metadata_guidance(profile: StandardProfile) -> tuple[str, str]:
    """Return JSON example + instructions for standard-specific metadata."""
    if profile.id == "ISO_26262":
        return (
            (
                '{"severity_class": "S2", "exposure_class": "E3", '
                '"controllability_class": "C2", "asil": "ASIL_B"}'
            ),
            (
                "Because this is ISO 26262, use the numeric scores as S/E/C proxies "
                "and include `severity_class`, `exposure_class`, "
                "`controllability_class`, and derived `asil` in `standard_metadata` "
                "using QM or ASIL_A through ASIL_D."
            ),
        )
    if profile.id == "MIL_STD_1629":
        return (
            '{"criticality_category": "Category_II", "probability_level": "Probable"}',
            (
                "Because this is MIL-STD-1629, include a `criticality_category` key "
                "in `standard_metadata` using Category_I through Category_IV, plus a "
                "`probability_level` describing the failure likelihood."
            ),
        )
    if profile.id == "AIAG_FMEA4":
        return (
            '{"special_characteristic": "SAFETY"}',
            (
                "For AIAG FMEA-4, use `standard_metadata` when a failure mode carries "
                "special customer or safety significance."
            ),
        )
    return (
        "{}",
        "Leave `standard_metadata` empty unless the selected standard adds extra context.",
    )


def format_standard_metadata(metadata: dict[str, Any]) -> str:
    """Render standard metadata consistently for tables and Markdown."""
    if not metadata:
        return ""
    items = []
    for key in sorted(metadata):
        value = metadata[key]
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, sort_keys=True)
        else:
            rendered = str(value)
        items.append(f"{key}={rendered}")
    return ", ".join(items)


def is_high_risk(rpn: int, threshold: int) -> bool:
    """Return True when the row exceeds the active standard's high-risk threshold."""
    return rpn >= threshold


def get_score_display_names(profile: StandardProfile) -> dict[str, str]:
    """Return human-readable score names for the active standard."""
    return _SCORE_DISPLAY_NAMES.get(profile.id, _SCORE_DISPLAY_NAMES["IEC_60812"])


def get_score_short_labels(profile: StandardProfile) -> dict[str, str]:
    """Return compact score labels used in tables and summaries."""
    return _SCORE_SHORT_LABELS.get(profile.id, _SCORE_SHORT_LABELS["IEC_60812"])


def get_score_header_labels(profile: StandardProfile) -> dict[str, str]:
    """Return combined long/short labels for exporter headers."""
    names = get_score_display_names(profile)
    short = get_score_short_labels(profile)
    return {
        field: f"{names[field]} ({short[field]})"
        for field in ("severity", "occurrence", "detection")
    }


def build_standard_score_guidance(profile: StandardProfile) -> str:
    """Build prompt guidance for the numeric scoring fields."""
    names = get_score_display_names(profile)
    labels = get_score_short_labels(profile)
    parts = []

    for field in ("severity", "occurrence", "detection"):
        scale = profile.scales.get(field)
        if not scale:
            continue
        parts.append(
            f"{names[field]} ({labels[field]}): {_format_scale_summary(scale)}"
        )

    if profile.id == "ISO_26262":
        parts.append(
            "Interpret the numeric fields as proxies for Severity, Exposure, and "
            "Controllability. Reflect the mapped S/E/C classes and derived ASIL in "
            "`standard_metadata`."
        )
    elif profile.id == "MIL_STD_1629":
        parts.append(
            "Interpret occurrence as mission probability, and record the derived "
            "criticality category and probability level in `standard_metadata`."
        )
    elif profile.id == "AIAG_FMEA4":
        parts.append(
            "Use classic AIAG S/O/D scoring and capture any special characteristics "
            "in `standard_metadata` when applicable."
        )

    return "\n".join(parts)


def build_high_risk_rule(
    profile: StandardProfile,
    threshold: int | None = None,
) -> str:
    """Return a prompt-friendly description of the active high-risk rule."""
    label = build_high_risk_label(profile, threshold)
    return f"Treat a row as high risk when it meets: {label}."


def build_high_risk_label(
    profile: StandardProfile,
    threshold: int | None = None,
) -> str:
    """Return a user-facing label for the active high-risk rule."""
    active_threshold = threshold or profile.high_risk_threshold
    if profile.id == "ISO_26262":
        return f"ASIL C/D or RPN >= {active_threshold}"
    if profile.id == "MIL_STD_1629":
        return f"Category I/II or RPN >= {active_threshold}"
    return f"RPN >= {active_threshold}"


def is_high_risk_row(
    row: Any,
    standard: str | StandardProfile,
    threshold: int | None = None,
) -> bool:
    """Return True when a row is high risk for the active standard."""
    profile = (
        standard
        if isinstance(standard, StandardProfile)
        else load_standard_profile(standard)
    )
    active_threshold = threshold or profile.high_risk_threshold

    metadata = _extract_row_value(row, "standard_metadata") or {}
    for key, values in _HIGH_RISK_METADATA_RULES.get(profile.id, {}).items():
        if metadata.get(key) in values:
            return True

    rpn = int(_extract_row_value(row, "rpn") or 0)
    return is_high_risk(rpn, active_threshold)


def count_high_risk_rows(
    rows: list[Any],
    standard: str | StandardProfile,
    threshold: int | None = None,
) -> int:
    """Count high-risk rows using the active standard's rules."""
    return sum(
        1
        for row in rows
        if is_high_risk_row(row, standard=standard, threshold=threshold)
    )


def _load_config(config_dir: str | Path | None) -> dict[str, Any]:
    """Load standards.yaml when PyYAML is available; otherwise return empty."""
    base = Path(config_dir) if config_dir else _DEFAULT_CONFIG_DIR
    path = base / "standards.yaml"
    if not path.exists():
        return {}
    try:
        import yaml

        with open(path, encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except ImportError:
        logger.debug("PyYAML not installed; using built-in standard defaults")
        return {}
    except Exception as exc:
        logger.warning("Failed to load %s: %s", path, exc)
        return {}


def _format_scale_summary(scale: dict[str, Any]) -> str:
    """Summarise a scale mapping for prompt injection."""
    parts = []
    for key, value in list(scale.items())[:4]:
        parts.append(f"{key}: {value}")
    return "; ".join(parts)


def _extract_row_value(row: Any, field: str) -> Any:
    """Extract a field from either an object or mapping."""
    if isinstance(row, dict):
        return row.get(field)
    return getattr(row, field, None)
