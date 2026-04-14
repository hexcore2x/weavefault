# WeaveFault — Architecture

## Overview

WeaveFault is organised as a linear five-stage pipeline:

```
Diagram File
     │
     ▼
┌──────────────────┐
│  Ingestion Layer │  Parse diagram → structured DiagramGraph
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Graph Layer     │  Build NetworkX DiGraph → cascade simulation → criticality
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Reasoning Layer │  LLM FMEA generation → RPN scoring → RAG retrieval
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Output Layer    │  Excel / Markdown / JSON export → diff engine
└──────────────────┘
```

---

## Package Map

```
src/weavefault/
├── __init__.py                  Public API surface
│
├── cli/
│   └── main.py                  Click CLI: generate / diff / watch
│
├── ingestion/
│   ├── schema.py                Pydantic v2 data models
│   ├── diagram_parser.py        Vision LLM extraction (PNG/SVG/drawio/PDF)
│   └── file_loader.py           File extension routing
│
├── graph/
│   ├── builder.py               NetworkX DiGraph + centrality metrics
│   ├── propagation.py           BFS cascade simulator
│   └── criticality.py           SPOF detection + criticality scoring
│
├── reasoning/
│   ├── fmea_generator.py        Graph-aware LLM prompt → FMEARow list
│   ├── rpn_scorer.py            Second-pass LLM RPN validation
│   ├── rag_retriever.py         ChromaDB vector retrieval
│   └── reasoning_chain.py       Audit trail datastructures
│
└── output/
    ├── fmea_formatter.py        Standard-specific column ordering
    ├── excel_exporter.py        .xlsx export with colour-coded RPN
    ├── markdown_exporter.py     .md export with Mermaid graph
    └── diff_engine.py           FMEA snapshot diff + Markdown report
```

---

## Data Models

All core data structures live in `ingestion/schema.py` and are Pydantic v2 models.

### DiagramGraph
```
DiagramGraph
 ├── id: str                     UUID hex
 ├── components: list[Component]
 ├── edges: list[Edge]
 ├── domain: str                 cloud | embedded | mechanical | hybrid
 ├── source_file: str
 ├── confidence: float           0.0–1.0 extraction quality
 └── raw_llm_response: str       Full LLM output for audit
```

### Component
```
Component
 ├── id: str                     Lowercase underscore slug
 ├── name: str                   Display name
 ├── component_type: ComponentType
 ├── description: str
 ├── is_external: bool
 └── is_critical: bool           Set by CriticalityAnalyzer
```

### FMEARow
```
FMEARow
 ├── id: str
 ├── component_id: str
 ├── component_name: str
 ├── failure_mode: str
 ├── potential_effect: str
 ├── cascade_effects: list[str]
 ├── severity: int               1–10
 ├── occurrence: int             1–10
 ├── detection: int              1–10
 ├── rpn: int                    auto-computed = S × O × D
 ├── recommended_action: str
 ├── standard_clause: str
 ├── reasoning_chain: str        Full LLM audit trail
 ├── confidence: float
 └── generated_by: str          Model ID
```

### CascadeChain (graph/propagation.py)
```
CascadeChain
 ├── origin_id: str
 ├── origin_name: str
 ├── affected_nodes: list[str]
 ├── paths: list[list[str]]      Every BFS path from origin
 ├── max_depth: int
 └── blast_radius_pct: float    % of graph affected
```

---

## Pipeline Detail

### 1. Ingestion

`DiagramParser.parse(file_path)` routes to one of four sub-parsers:

| Format | Method | Mechanism |
|--------|--------|-----------|
| PNG/JPG | `_parse_image` | Base64-encode → Vision LLM → JSON |
| SVG | `_parse_svg` | Extract text labels + cairosvg → PNG → Vision LLM |
| drawio/XML | `_parse_drawio` | Deterministic XML parse of mxCell elements |
| PDF | `_parse_pdf` | PyMuPDF page render → PNG → Vision LLM |

The vision prompt instructs the LLM to return a strict JSON object matching the `DiagramGraph` schema. Markdown fences are stripped before parsing.

### 2. Graph Layer

`GraphBuilder.build(diagram)` creates a `networkx.DiGraph` with:
- Node attributes: `name`, `component_type`, `in_degree`, `out_degree`, `betweenness_centrality`, `is_isolated`
- Edge attributes: `label`, `protocol`, `data_flow`, `bidirectional`

`CascadeSimulator.simulate(graph, origin_id)` runs BFS from the origin node following directed successors. It returns a `CascadeChain` with blast radius as a percentage of total graph size.

`CriticalityAnalyzer.analyze(graph, cascades)` computes a composite score:

```
score = 0.40 × betweenness_centrality
      + 0.40 × blast_radius_pct / 100
      + 0.20 × in_degree / max_in_degree
```

SPOFs (single points of failure) receive a +0.15 bonus. Score maps to tiers: CRITICAL ≥ 0.70 → HIGH ≥ 0.45 → MEDIUM ≥ 0.20 → LOW.

### 3. Reasoning Layer

`FMEAGenerator.generate(...)` iterates every component and builds a structured prompt containing:
- Component metadata + type
- Topology context (sends_to / receives_from)
- Cascade impact summary from `CascadeSimulator`
- Criticality tier and SPOF flag
- RAG context (past FMEA examples from ChromaDB)

The LLM returns a JSON array of 3–5 `FMEARow` objects per component.

`RPNScorer.score_all(rows)` performs a second LLM pass that reviews each row for score consistency and may adjust Severity/Occurrence/Detection.

### 4. Output Layer

`ExcelExporter` produces a styled `.xlsx` with:
- FMEA sheet: colour-coded RPN (red ≥ 200, orange ≥ 100, green < 100)
- Summary sheet: key metrics + top-3 highest RPN

`MarkdownExporter` produces a `.md` with YAML front-matter, tables, and an embedded Mermaid dependency graph.

`FMEADiffEngine.diff(before, after)` matches rows by `component_id + failure_mode` key and classifies each as new, removed, changed, or unchanged.

---

## Configuration

| File | Purpose |
|------|---------|
| `config/domains.yaml` | Domain-specific component types, failure modes, detection methods |
| `config/standards.yaml` | RPN thresholds, scoring scales, standard references |
| `.env` | API keys, model selection, ChromaDB path |

See [configuration.md](configuration.md) for full reference.

---

## LLM Provider Support

| Provider | Text Models | Vision Models |
|----------|------------|--------------|
| Anthropic | `claude-opus-4-6`, `claude-sonnet-4-6` | Same |
| OpenAI | `gpt-4o`, `gpt-4-turbo` | Same |

Provider and model are set via `LLM_PROVIDER` and `LLM_MODEL` environment variables or `--provider` / `--model` CLI flags.
