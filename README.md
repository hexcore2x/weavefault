```
██╗    ██╗███████╗ █████╗ ██╗   ██╗███████╗███████╗ █████╗ ██╗   ██╗██╗  ████████╗
██║    ██║██╔════╝██╔══██╗██║   ██║██╔════╝██╔════╝██╔══██╗██║   ██║██║  ╚══██╔══╝
██║ █╗ ██║█████╗  ███████║██║   ██║█████╗  █████╗  ███████║██║   ██║██║     ██║
██║███╗██║██╔══╝  ██╔══██║╚██╗ ██╔╝██╔══╝  ██╔══╝  ██╔══██║██║   ██║██║     ██║
╚███╔███╔╝███████╗██║  ██║ ╚████╔╝ ███████╗██║     ██║  ██║╚██████╔╝███████╗██║
 ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝
```

> **"We weave through your architecture to find where it will fault."**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/weavefault.svg)](https://pypi.org/project/weavefault/)

---

## What is WeaveFault?

**WeaveFault** is an automated FMEA (Failure Mode & Effects Analysis) generator that:

1. **Reads your architecture diagrams** — PNG, SVG, drawio, PDF
2. **Builds a dependency graph** — using NetworkX, with centrality metrics
3. **Simulates failure propagation** — BFS cascade through the directed graph
4. **Generates structured FMEA documents** — AIAG, IEC 60812, MIL-STD-1629, ISO 26262
5. **Shows full AI reasoning chains** — every RPN score is fully auditable

WeaveFault is **diagram-native**, **git-integrated**, **cross-domain**, and **glass-box**.

---

## The 5 Pillars

### 1. Topology-First Input
Your architecture diagram *is* your failure map. WeaveFault extracts every component,
edge, and data flow — then reasons about failure from the structure of the system itself,
not from a blank spreadsheet.

### 2. Cascade Failure Graph
Failures don't happen in isolation. WeaveFault simulates propagation through your
dependency graph using directed BFS, computing blast radius, critical paths, and
single points of failure (SPOFs) before a single FMEA row is written.

### 3. Living FMEA (Git-Native, Diffs on Commit)
FMEA documents are checked into git alongside diagrams. When diagrams change,
WeaveFault regenerates and produces a structured diff report — showing exactly
which failure modes are new, removed, or changed. Your FMEA evolves with your system.

### 4. Cross-Domain Reasoning
WeaveFault supports cloud infrastructure, embedded firmware, mechanical systems, and
hybrid architectures. Domain-specific failure modes, standards, and severity contexts
are configurable via `config/domains.yaml`.

### 5. Glass-Box AI
Every FMEA row includes the full LLM reasoning chain that produced it. Severity,
Occurrence, and Detection scores are not black boxes — they are justified, auditable,
and can be challenged in code review.

---

## Installation

```bash
pip install weavefault
```

Or from source:

```bash
git clone https://github.com/Hexcore2x/weavefault.git
cd weavefault
pip install -e .
```

Set up your environment:

```bash
cp .env.example .env
# Edit .env and add your API keys
```

---

## Quick Start

```bash
# Generate FMEA from a diagram
weavefault generate \
  --diagram ./diagrams/auth_service.png \
  --domain  cloud \
  --output  ./fmea/ \
  --format  excel

# Diff two FMEA snapshots
weavefault diff \
  --before ./fmea/v1.md \
  --after  ./fmea/v2.md \
  --output ./fmea/diff_report.md

# Watch diagram folder and auto-regenerate on change
weavefault watch \
  --diagram ./diagrams/ \
  --output  ./fmea/ \
  --branch  main
```

---

## CLI Reference

### `weavefault generate`

Parse a diagram, run cascade simulation, generate FMEA, and export.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--diagram` | PATH | required | Input diagram file or directory |
| `--domain` | TEXT | `cloud` | System domain (cloud/embedded/mechanical/hybrid) |
| `--standard` | TEXT | `IEC_60812` | FMEA standard to apply |
| `--output` | PATH | required | Output directory |
| `--format` | CHOICE | `both` | Export format: excel, markdown, both |
| `--provider` | TEXT | env | LLM provider (anthropic/openai) |
| `--model` | TEXT | env | LLM model name |
| `--verbose` | FLAG | false | Enable verbose logging |

### `weavefault diff`

Compare two FMEA snapshots and produce a diff report.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--before` | PATH | required | First FMEA snapshot (.weavefault.json or .md) |
| `--after` | PATH | required | Second FMEA snapshot |
| `--output` | PATH | required | Output path for diff report (.md) |

### `weavefault watch`

Monitor a diagram directory and regenerate FMEA on every change.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--diagram` | PATH | required | Directory to watch |
| `--output` | PATH | required | Output directory |
| `--interval` | INT | `2` | Poll interval in seconds |

---

## How It Works

```
Architecture Diagram
        │
        ▼
┌─────────────────┐
│  DiagramParser  │  Vision LLM extracts components + edges
│  (PNG/SVG/etc)  │  → DiagramGraph (Pydantic model)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  GraphBuilder   │  NetworkX DiGraph
│  + Centrality   │  Betweenness, in/out-degree, SPOFs
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ CascadeSimulator│  BFS propagation per node
│  blast radius   │  → CascadeChain per component
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ FMEAGenerator   │  Graph-aware LLM prompts
│  + RAG context  │  3-5 failure modes per component
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  RPNScorer      │  Severity × Occurrence × Detection
│  + ReasonChain  │  Full audit trail per row
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Exporters      │  .xlsx / .md / .weavefault.json
│  + DiffEngine   │  Git-native diff reports
└─────────────────┘
```

---

## Supported Domains

| Domain | Description | Example Systems |
|--------|-------------|-----------------|
| `cloud` | Cloud-native microservices, APIs, databases | AWS, GCP, K8s architectures |
| `embedded` | Real-time firmware, sensors, actuators | IoT, automotive ECU, RTOS |
| `mechanical` | Physical systems, manufacturing, materials | CNC, pneumatics, structural |
| `hybrid` | Multi-domain systems | Connected vehicles, smart factories |

---

## Supported Standards

| Standard | Full Name | Domain | RPN High-Risk |
|----------|-----------|--------|---------------|
| `AIAG_FMEA4` | AIAG FMEA-4 | Automotive | ≥ 100 |
| `IEC_60812` | IEC 60812:2018 | General / Industrial | ≥ 200 |
| `MIL_STD_1629` | MIL-STD-1629A | Defense / Aerospace | ≥ 200 |
| `ISO_26262` | ISO 26262:2018 | Functional Safety / Automotive | ASIL-based |

---

## Uploading to GitHub Later

When you are ready to push this project to GitHub:

```bash
git remote add origin https://github.com/Hexcore2x/weavefault.git
git add .
git commit -m "feat: initial WeaveFault project"
git push -u origin main
```

The GitHub Actions workflow at `.github/workflows/weavefault-ci.yml` will activate
automatically on push and begin auto-generating FMEA on diagram changes.

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make your changes with tests
4. Run `black src/ tests/` and `ruff check src/ tests/`
5. Submit a pull request

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

*WeaveFault is built on the belief that every architecture diagram is a failure map waiting to be read.*
