"""
WeaveFault DiagramParser — Vision LLM extraction from architecture diagrams.

Supports PNG, JPG, SVG, drawio/XML, and PDF inputs.
Integrates with Anthropic (claude-opus-4-6) and OpenAI (gpt-4o) vision APIs.
"""
from __future__ import annotations

import base64
import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING, Any

from weavefault.ingestion.file_loader import get_file_type
from weavefault.ingestion.schema import (
    Component,
    ComponentType,
    DiagramGraph,
    Edge,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DiagramParseError(ValueError):
    """Raised when a diagram cannot be converted into a usable DiagramGraph."""


class DiagramParser:
    """
    Parse architecture diagrams into structured DiagramGraph objects.

    Supports multiple input formats and LLM providers.
    """

    def __init__(self, provider: str, vision_model: str, api_key: str) -> None:
        """
        Initialise the DiagramParser.

        Args:
            provider: LLM provider — 'anthropic' or 'openai'.
            vision_model: Model ID to use for vision tasks.
            api_key: API key for the chosen provider.
        """
        self.provider = provider.lower()
        self.vision_model = vision_model
        self.api_key = api_key

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def parse(self, file_path: str) -> DiagramGraph:
        """
        Parse a diagram file into a DiagramGraph.

        Routes to the correct parser based on file extension.

        Args:
            file_path: Path to the diagram file.

        Returns:
            A validated DiagramGraph instance.
        """
        file_type = get_file_type(file_path)
        logger.info("Parsing %s as %s", file_path, file_type)

        if file_type == "image":
            graph = self._parse_image(file_path)
        elif file_type == "svg":
            graph = self._parse_svg(file_path)
        elif file_type == "drawio":
            graph = self._parse_drawio(file_path)
        elif file_type == "pdf":
            graph = self._parse_pdf(file_path)
        else:
            raise ValueError(f"Unknown file type: {file_type!r}")

        graph.source_file = str(Path(file_path).resolve())
        if not graph.components:
            raise DiagramParseError(
                f"No components could be extracted from {Path(file_path).name}."
            )
        logger.info(
            "Parsed %d components, %d edges (confidence=%.2f)",
            len(graph.components),
            len(graph.edges),
            graph.confidence,
        )
        return graph

    # ──────────────────────────────────────────────────────────────
    # Format-specific parsers
    # ──────────────────────────────────────────────────────────────

    def _parse_image(self, path: str) -> DiagramGraph:
        """Parse a raster image (PNG/JPG) using the vision LLM."""
        image_b64 = self._encode_image(path)
        prompt = self._build_vision_prompt()
        media_type = self._get_media_type(path)

        if self.provider == "anthropic":
            response = self._call_anthropic(prompt, image_b64, media_type)
        elif self.provider == "openai":
            response = self._call_openai(prompt, image_b64, media_type)
        else:
            raise ValueError(f"Unknown provider: {self.provider!r}")

        return self._parse_llm_response(response, source_file=path)

    def _parse_svg(self, path: str) -> DiagramGraph:
        """
        Parse an SVG diagram.

        Extracts text labels from the SVG XML, then converts to PNG and
        passes through the vision LLM for structural understanding.
        """
        import cairosvg  # lazy import — not always installed

        svg_labels = self._extract_svg_text_labels(path)
        logger.debug("SVG text labels: %s", svg_labels)

        # Convert SVG → PNG in memory
        png_bytes = cairosvg.svg2png(url=path)
        png_path = Path(path).with_suffix(".tmp.png")
        try:
            png_path.write_bytes(png_bytes)
            graph = self._parse_image(str(png_path))
        finally:
            if png_path.exists():
                png_path.unlink()

        # Merge SVG text labels to improve component names
        cmap = {c.id: c for c in graph.components}
        for comp in graph.components:
            if comp.name in svg_labels:
                cmap[comp.id].description = f"[SVG label confirmed] {comp.description}"

        return graph

    def _parse_drawio(self, path: str) -> DiagramGraph:
        """
        Parse a draw.io (.drawio / .xml) file deterministically.

        Extracts components and edges from mxCell XML nodes without LLM,
        then uses LLM only for component type classification.
        """
        tree = ET.parse(path)
        root = tree.getroot()

        # draw.io XML namespace may or may not be present
        cells = root.findall(".//{*}mxCell") or root.findall(".//mxCell")

        components: list[Component] = []
        edges: list[Edge] = []
        id_to_label: dict[str, str] = {}

        for cell in cells:
            cell_id = cell.get("id", "")
            label = (cell.get("value") or "").strip()
            style = cell.get("style", "")
            source = cell.get("source", "")
            target = cell.get("target", "")
            vertex = cell.get("vertex", "0")
            edge_attr = cell.get("edge", "0")

            if not cell_id or cell_id in ("0", "1"):
                continue

            if edge_attr == "1" and source and target:
                edges.append(
                    Edge(
                        source_id=source,
                        target_id=target,
                        label=label,
                    )
                )
            elif vertex == "1" and label:
                slug = self._slugify(label) or cell_id
                id_to_label[cell_id] = slug
                comp_type = self._classify_component_type_heuristic(label, style)
                components.append(
                    Component(
                        id=slug,
                        name=label,
                        component_type=comp_type,
                    )
                )

        # Re-map edge source/target from cell IDs to slugs
        slug_map = id_to_label
        resolved_edges = []
        for e in edges:
            src = slug_map.get(e.source_id, e.source_id)
            tgt = slug_map.get(e.target_id, e.target_id)
            resolved_edges.append(Edge(source_id=src, target_id=tgt, label=e.label))

        return DiagramGraph(
            components=components,
            edges=resolved_edges,
            domain="cloud",
            confidence=0.95,  # deterministic parse → high confidence
        )

    def _parse_pdf(self, path: str) -> DiagramGraph:
        """Parse a PDF by extracting the first page as an image."""
        import fitz  # PyMuPDF — lazy import

        doc = fitz.open(path)
        page = doc[0]
        pix = page.get_pixmap(dpi=150)
        img_path = Path(path).with_suffix(".tmp.png")
        try:
            pix.save(str(img_path))
            graph = self._parse_image(str(img_path))
        finally:
            doc.close()
            if img_path.exists():
                img_path.unlink()
        return graph

    # ──────────────────────────────────────────────────────────────
    # Vision prompt
    # ──────────────────────────────────────────────────────────────

    def _build_vision_prompt(self) -> str:
        """
        Build the structured JSON extraction prompt for the vision LLM.

        Returns a prompt that instructs the model to return ONLY valid JSON.
        """
        return """Analyze this architecture diagram carefully.

Extract ALL of the following and return ONLY valid JSON — no markdown,
no explanation, no preamble:

{
  "components": [
    {
      "id": "unique_slug",
      "name": "Component Name",
      "component_type": "SERVICE|DATABASE|QUEUE|GATEWAY|SENSOR|ACTUATOR|NETWORK|STORAGE|CACHE|LOADBALANCER|UNKNOWN",
      "description": "brief role in the system",
      "is_external": true,
      "x": null,
      "y": null,
      "metadata": {}
    }
  ],
  "edges": [
    {
      "source_id": "slug_of_source",
      "target_id": "slug_of_target",
      "label": "optional label on arrow",
      "bidirectional": false,
      "data_flow": "what data flows here",
      "protocol": "HTTP|gRPC|TCP|MQTT|CAN|etc"
    }
  ],
  "confidence": 0.0,
  "domain": "cloud|embedded|mechanical|hybrid"
}

Rules:
- Every visible box, service, database, sensor = one component entry
- Every arrow or connection = one edge
- Use directional edges (source sends to target)
- Mark components outside the main boundary as is_external: true
- confidence = your honest estimate of extraction accuracy (0.0 to 1.0)
- id must be a lowercase slug with underscores, unique per component
- Return nothing except the JSON object"""

    # ──────────────────────────────────────────────────────────────
    # LLM provider calls
    # ──────────────────────────────────────────────────────────────

    def _encode_image(self, path: str) -> str:
        """Base64-encode an image file."""
        with open(path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")

    def _call_anthropic(self, prompt: str, image_b64: str, media_type: str) -> str:
        """Call the Anthropic vision API."""
        import anthropic  # lazy import

        client = anthropic.Anthropic(api_key=self.api_key)
        message = client.messages.create(
            model=self.vision_model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return message.content[0].text

    def _call_openai(self, prompt: str, image_b64: str, media_type: str) -> str:
        """Call the OpenAI vision API."""
        import openai  # lazy import

        client = openai.OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.vision_model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{image_b64}",
                                "detail": "high",
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return response.choices[0].message.content or ""

    # ──────────────────────────────────────────────────────────────
    # Response parsing
    # ──────────────────────────────────────────────────────────────

    def _parse_llm_response(self, response: str, source_file: str) -> DiagramGraph:
        """
        Parse the LLM JSON response into a DiagramGraph.

        Strips markdown fences if present before JSON parsing.
        """
        # Strip markdown code fences if the model wrapped the JSON
        clean = response.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data: dict[str, Any] = json.loads(clean)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse LLM response as JSON: %s", exc)
            logger.debug("Raw response: %s", response[:500])
            raise DiagramParseError(
                "Vision model did not return valid JSON for the diagram parse."
            )

        components = [
            Component(**c) for c in data.get("components", []) if isinstance(c, dict)
        ]
        edges = [Edge(**e) for e in data.get("edges", []) if isinstance(e, dict)]

        return DiagramGraph(
            components=components,
            edges=edges,
            domain=data.get("domain", "cloud"),
            confidence=float(data.get("confidence", 0.0)),
            raw_llm_response=response,
            source_file=source_file,
        )

    # ──────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────

    def _extract_svg_text_labels(self, path: str) -> list[str]:
        """Extract all text content from SVG <text> elements."""
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            ns = {"svg": "http://www.w3.org/2000/svg"}
            texts = [
                (elem.text or "").strip()
                for elem in root.findall(".//svg:text", ns)
                if elem.text
            ]
            return [t for t in texts if t]
        except ET.ParseError:
            return []

    @staticmethod
    def _get_media_type(path: str) -> str:
        """Resolve the correct MIME type for image uploads."""
        suffix = Path(path).suffix.lower()
        if suffix == ".png":
            return "image/png"
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".svg":
            return "image/svg+xml"
        raise ValueError(f"Unsupported image media type for {path!r}")

    @staticmethod
    def _slugify(label: str) -> str:
        """Convert a display label to a lowercase underscore slug."""
        import re

        slug = re.sub(r"[^a-zA-Z0-9]+", "_", label.lower()).strip("_")
        return slug[:64]  # cap length

    @staticmethod
    def _classify_component_type_heuristic(label: str, style: str) -> ComponentType:
        """
        Classify a draw.io cell's component type from its label and style
        without calling the LLM.
        """
        lower = label.lower()
        if any(kw in lower for kw in ("db", "database", "postgres", "mysql", "mongo")):
            return ComponentType.DATABASE
        if any(kw in lower for kw in ("queue", "kafka", "rabbitmq", "sqs", "pubsub")):
            return ComponentType.QUEUE
        if any(kw in lower for kw in ("cache", "redis", "memcache")):
            return ComponentType.CACHE
        if any(kw in lower for kw in ("gateway", "api gw", "apigw")):
            return ComponentType.GATEWAY
        if any(kw in lower for kw in ("lb", "load balancer", "nginx", "haproxy")):
            return ComponentType.LOADBALANCER
        if any(kw in lower for kw in ("storage", "s3", "blob", "gcs", "minio")):
            return ComponentType.STORAGE
        if any(kw in lower for kw in ("sensor",)):
            return ComponentType.SENSOR
        if any(kw in lower for kw in ("actuator",)):
            return ComponentType.ACTUATOR
        if any(kw in lower for kw in ("network", "vpc", "subnet", "vlan")):
            return ComponentType.NETWORK
        return ComponentType.SERVICE
