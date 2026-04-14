# Changelog

All notable changes to WeaveFault will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Initial public release of WeaveFault

---

## [0.1.0] — 2024-04-12

### Added

#### Core pipeline
- `DiagramParser` — Vision LLM extraction for PNG, JPG, SVG, draw.io, and PDF diagrams
- `GraphBuilder` — NetworkX DiGraph construction with betweenness centrality, in/out-degree, and isolation metrics
- `CascadeSimulator` — BFS failure propagation with blast radius calculation and worst-failure ranking
- `CriticalityAnalyzer` — SPOF detection via connected-component analysis; composite criticality scoring (topology + cascade + degree); CRITICAL / HIGH / MEDIUM / LOW tier assignment
- `FMEAGenerator` — Graph-aware LLM prompts with topology context, cascade impact summary, and RAG retrieval; generates 3–5 failure modes per component
- `RPNScorer` — Second-pass LLM review and adjustment of Severity / Occurrence / Detection scores
- `RAGRetriever` — ChromaDB-backed semantic retrieval of past FMEA examples and standards references; graceful degradation when ChromaDB is unavailable

#### Output
- `ExcelExporter` — Styled `.xlsx` workbook with colour-coded RPN cells (red ≥ 200, orange ≥ 100, green < 100) and summary sheet
- `MarkdownExporter` — Git-friendly `.md` with YAML front-matter, summary table, FMEA table, embedded Mermaid dependency graph, and high-risk section
- `FMEADiffEngine` — Row-by-row diff across two FMEA snapshots; structured Markdown diff report

#### CLI
- `weavefault generate` — End-to-end FMEA generation from a diagram file
- `weavefault diff` — Compare two `.weavefault.json` snapshots
- `weavefault watch` — File-system watcher that auto-regenerates FMEA on diagram change

#### Configuration
- `config/domains.yaml` — Domain-specific component types, failure modes, severity context, and detection methods for `cloud`, `embedded`, `mechanical`, `hybrid`
- `config/standards.yaml` — RPN thresholds and scoring scales for `IEC_60812`, `AIAG_FMEA4`, `MIL_STD_1629`, `ISO_26262`

#### Scripts
- `scripts/setup_rag.py` — Index built-in corpus of 14 FMEA examples + 4 standards references into ChromaDB
- `scripts/generate_sample.py` — Generate a complete sample FMEA from a built-in 6-node architecture without an API key

#### DevOps
- GitHub Actions CI workflow with lint, test (Python 3.11 + 3.12), coverage, build smoke test, and PyPI release job
- Pre-commit configuration (ruff, black, YAML/TOML validation, large-file check, private-key detection)
- Makefile with `install`, `test`, `test-cov`, `lint`, `fmt`, `sample`, `rag-setup`, `build`, `clean`

#### Documentation
- `docs/architecture.md` — Full pipeline walkthrough, package map, and data model reference
- `docs/quickstart.md` — Installation, configuration, and usage guide
- `docs/configuration.md` — Complete environment variable and config file reference

#### Tests
- 9 test modules with 100+ test cases covering GraphBuilder, CascadeSimulator, CriticalityAnalyzer, DiagramParser, FMEAGenerator, FMEADiffEngine, FMEAFormatter, ExcelExporter, MarkdownExporter, RAGRetriever, file_loader, and CLI commands
- Shared `conftest.py` with reusable diagram, graph, cascade, and document fixtures

### Fixed
- Removed duplicate `CascadeChain` dataclass definition that existed in both `schema.py` and `propagation.py`

### Technical
- Python 3.11+ required
- Pydantic v2 for all data models
- Lazy imports for heavy optional dependencies (`cairosvg`, `fitz`, `chromadb`, `anthropic`, `openai`) to keep startup fast
- `FMEADocument.save()` persists full document as `.weavefault.json` for diff and audit

---

[Unreleased]: https://github.com/Hexcore2x/weavefault/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Hexcore2x/weavefault/releases/tag/v0.1.0
