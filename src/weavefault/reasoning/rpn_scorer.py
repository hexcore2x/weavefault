"""
WeaveFault RPNScorer - LLM-based review and adjustment of RPN scores.
"""

from __future__ import annotations

import json
import logging

from weavefault.ingestion.schema import FMEARow
from weavefault.standards import (
    build_high_risk_rule,
    build_standard_prompt_context,
    build_standard_score_guidance,
    canonical_standard_name,
    get_score_display_names,
    load_standard_profile,
)

logger = logging.getLogger(__name__)


class RPNScorer:
    """
    Validate and refine RPN scores for a list of FMEA rows.

    Performs a second-pass LLM review that checks score consistency
    against the system domain, standard, and cascade context.
    """

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        standard: str = "IEC_60812",
        domain: str = "cloud",
        config_dir: str | None = None,
    ) -> None:
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key
        self.standard = canonical_standard_name(standard)
        self.domain = domain
        self.standard_profile = load_standard_profile(self.standard, config_dir)

    def score_all(self, rows: list[FMEARow]) -> list[FMEARow]:
        """Review and validate all FMEA rows."""
        if not rows:
            return rows

        reviewed: list[FMEARow] = []
        for row in rows:
            try:
                reviewed.append(self._review_row(row))
            except Exception as exc:
                logger.warning(
                    "RPN review failed for %s / %s: %s",
                    row.component_name,
                    row.failure_mode,
                    exc,
                )
                reviewed.append(row)

        return reviewed

    def _review_row(self, row: FMEARow) -> FMEARow:
        """Review a single FMEA row and return an updated version."""
        prompt = self._build_review_prompt(row)
        try:
            response = self._call_llm(prompt)
            clean = response.strip()
            if clean.startswith("```"):
                lines = clean.split("\n")
                clean = "\n".join(
                    lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                )
            data = json.loads(clean)
            updated_data = row.model_dump()
            for field in ("severity", "occurrence", "detection", "reasoning_chain"):
                if field in data:
                    updated_data[field] = data[field]
            if isinstance(data.get("standard_metadata"), dict):
                updated_data["standard_metadata"] = data["standard_metadata"]
            return FMEARow(**updated_data)
        except Exception as exc:
            logger.debug("RPNScorer parse error: %s", exc)
            return row

    def _build_review_prompt(self, row: FMEARow) -> str:
        """Build the RPN review prompt."""
        standard_context = build_standard_prompt_context(self.standard_profile)
        score_names = get_score_display_names(self.standard_profile)
        score_guide = build_standard_score_guidance(self.standard_profile)
        high_risk_rule = build_high_risk_rule(self.standard_profile)
        return f"""You are a senior reliability engineer reviewing FMEA scores.

STANDARD CONTEXT:
{standard_context}

FMEA ROW TO REVIEW:
Component: {row.component_name}
Failure mode: {row.failure_mode}
Potential effect: {row.potential_effect}
Cascade effects: {row.cascade_effects}
Standard metadata: {row.standard_metadata}

CURRENT SCORES:
{score_names['severity']}:   {row.severity}/10
{score_names['occurrence']}: {row.occurrence}/10
{score_names['detection']}:  {row.detection}/10
RPN:        {row.rpn}

DOMAIN: {self.domain}
STANDARD: {self.standard}

Review these scores for consistency. Consider:
- Is the {score_names['severity'].lower()} rating appropriate given the cascade effects?
- Is the {score_names['occurrence'].lower()} rating realistic for this component?
- Is the {score_names['detection'].lower()} rating justified?
- Preserve or refine any standard-specific metadata if needed.
- Apply this scoring guidance:
{score_guide}
- {high_risk_rule}

Return ONLY valid JSON with adjusted scores (or same if already correct):

{{
  "severity": <1-10>,
  "occurrence": <1-10>,
  "detection": <1-10>,
  "reasoning_chain": "brief explanation of any changes",
  "standard_metadata": {{"keep_or_adjust_any_standard_specific_classifications": true}}
}}"""

    def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM provider."""
        if self.provider == "anthropic":
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)
            message = client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text

        if self.provider == "openai":
            import openai

            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content or ""

        raise ValueError(f"Unknown provider: {self.provider!r}")
