"""
Tests for DiagramParser — focuses on the pure-Python parts that don't
require LLM API calls: _parse_llm_response, _build_vision_prompt, _slugify.
"""
from __future__ import annotations

import json

import pytest

from weavefault.ingestion.diagram_parser import DiagramParseError, DiagramParser
from weavefault.ingestion.schema import ComponentType, DiagramGraph


@pytest.fixture
def parser() -> DiagramParser:
    return DiagramParser(
        provider="anthropic",
        vision_model="claude-opus-4-6",
        api_key="test-key",
    )


def _make_valid_llm_response() -> str:
    return json.dumps(
        {
            "components": [
                {
                    "id": "api_gateway",
                    "name": "API Gateway",
                    "component_type": "GATEWAY",
                    "description": "Entry point for all requests",
                    "is_external": False,
                    "x": None,
                    "y": None,
                    "metadata": {},
                },
                {
                    "id": "auth_service",
                    "name": "Auth Service",
                    "component_type": "SERVICE",
                    "description": "Handles authentication",
                    "is_external": False,
                    "x": None,
                    "y": None,
                    "metadata": {},
                },
                {
                    "id": "user_db",
                    "name": "User DB",
                    "component_type": "DATABASE",
                    "description": "User records store",
                    "is_external": False,
                    "x": None,
                    "y": None,
                    "metadata": {},
                },
            ],
            "edges": [
                {
                    "source_id": "api_gateway",
                    "target_id": "auth_service",
                    "label": "auth request",
                    "bidirectional": False,
                    "data_flow": "JWT tokens",
                    "protocol": "HTTP",
                },
                {
                    "source_id": "auth_service",
                    "target_id": "user_db",
                    "label": "lookup",
                    "bidirectional": False,
                    "data_flow": "user records",
                    "protocol": "TCP",
                },
            ],
            "confidence": 0.92,
            "domain": "cloud",
        }
    )


class TestParseLlmResponse:
    def test_valid_json_produces_diagram_graph(self, parser: DiagramParser) -> None:
        response = _make_valid_llm_response()
        graph = parser._parse_llm_response(response, source_file="test.png")
        assert isinstance(graph, DiagramGraph)
        assert len(graph.components) == 3
        assert len(graph.edges) == 2
        assert graph.confidence == pytest.approx(0.92)
        assert graph.domain == "cloud"

    def test_component_types_parsed_correctly(self, parser: DiagramParser) -> None:
        graph = parser._parse_llm_response(
            _make_valid_llm_response(), source_file="test.png"
        )
        types = {c.id: c.component_type for c in graph.components}
        assert types["api_gateway"] == ComponentType.GATEWAY
        assert types["auth_service"] == ComponentType.SERVICE
        assert types["user_db"] == ComponentType.DATABASE

    def test_invalid_json_raises_parse_error(self, parser: DiagramParser) -> None:
        with pytest.raises(DiagramParseError):
            parser._parse_llm_response("not valid json", source_file="x.png")

    def test_markdown_fenced_json_is_stripped(self, parser: DiagramParser) -> None:
        raw = _make_valid_llm_response()
        fenced = f"```json\n{raw}\n```"
        graph = parser._parse_llm_response(fenced, source_file="x.png")
        assert len(graph.components) == 3

    def test_source_file_set_on_returned_graph(self, parser: DiagramParser) -> None:
        graph = parser._parse_llm_response(
            _make_valid_llm_response(), source_file="/path/to/diagram.png"
        )
        assert graph.source_file == "/path/to/diagram.png"


class TestBuildVisionPrompt:
    def test_prompt_contains_required_keys(self, parser: DiagramParser) -> None:
        prompt = parser._build_vision_prompt()
        assert "components" in prompt
        assert "edges" in prompt
        assert "confidence" in prompt
        assert "is_external" in prompt
        assert "component_type" in prompt

    def test_prompt_demands_valid_json_only(self, parser: DiagramParser) -> None:
        prompt = parser._build_vision_prompt()
        assert "valid JSON" in prompt
        assert "no markdown" in prompt.lower() or "no markdown" in prompt

    def test_prompt_is_nonempty_string(self, parser: DiagramParser) -> None:
        prompt = parser._build_vision_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 100


class TestSlugify:
    def test_simple_label(self) -> None:
        assert DiagramParser._slugify("Auth Service") == "auth_service"

    def test_special_characters(self) -> None:
        slug = DiagramParser._slugify("API Gateway (v2)")
        assert " " not in slug
        assert slug.islower()

    def test_max_length(self) -> None:
        long_label = "A" * 200
        assert len(DiagramParser._slugify(long_label)) <= 64

    def test_empty_string(self) -> None:
        assert DiagramParser._slugify("") == ""


class TestMediaTypes:
    def test_jpeg_media_type(self) -> None:
        assert DiagramParser._get_media_type("diagram.jpeg") == "image/jpeg"

    def test_png_media_type(self) -> None:
        assert DiagramParser._get_media_type("diagram.png") == "image/png"
