# WeaveFault — Quick Start

## Prerequisites

- Python 3.11+
- An Anthropic or OpenAI API key (for LLM-powered generation)

---

## 1. Install

```bash
# From PyPI
pip install weavefault

# From source (development)
git clone https://github.com/YOUR_USERNAME/weavefault.git
cd weavefault
pip install -e ".[dev]"
```

---

## 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and set your API key:

```bash
ANTHROPIC_API_KEY=sk-ant-...
LLM_PROVIDER=anthropic
LLM_MODEL=claude-opus-4-6
VISION_MODEL=claude-opus-4-6
```

---

## 3. Verify Installation (no API key needed)

Run the built-in sample generator to confirm everything is installed correctly:

```bash
python scripts/generate_sample.py
```

This creates a sample FMEA for a 6-node e-commerce checkout architecture in `./sample_output/` — no API key or diagram required.

---

## 4. Set Up RAG Corpus (recommended)

Index built-in FMEA examples and standards into ChromaDB:

```bash
python scripts/setup_rag.py
```

This creates a `./chroma_db/` directory with pre-loaded FMEA examples.
The corpus significantly improves FMEA generation quality.

---

## 5. Generate FMEA from a Diagram

### PNG / JPG

```bash
weavefault generate \
  --diagram ./diagrams/auth_service.png \
  --domain  cloud \
  --output  ./fmea/ \
  --format  both
```

### SVG

```bash
weavefault generate \
  --diagram ./diagrams/embedded_system.svg \
  --domain  embedded \
  --standard IEC_60812 \
  --output  ./fmea/
```

### draw.io

```bash
weavefault generate \
  --diagram ./diagrams/architecture.drawio \
  --domain  cloud \
  --output  ./fmea/
```

### PDF

```bash
weavefault generate \
  --diagram ./docs/system_architecture.pdf \
  --domain  mechanical \
  --standard AIAG_FMEA4 \
  --output  ./fmea/
```

---

## 6. Diff Two FMEA Snapshots

When a diagram changes, regenerate and compare:

```bash
# Regenerate with new diagram
weavefault generate --diagram ./diagrams/v2.png --output ./fmea/v2/

# Diff against previous snapshot
weavefault diff \
  --before ./fmea/v1/abc12345.weavefault.json \
  --after  ./fmea/v2/def67890.weavefault.json \
  --output ./fmea/diff_v1_v2.md
```

---

## 7. Watch Mode (auto-regenerate)

Monitor a diagram folder and regenerate FMEA whenever a diagram changes:

```bash
weavefault watch \
  --diagram ./diagrams/ \
  --output  ./fmea/ \
  --interval 2
```

---

## Output Files

After running `generate`, three files are written to the output directory:

| File | Description |
|------|-------------|
| `fmea_<id>.xlsx` | Excel workbook with colour-coded RPN cells |
| `fmea_<id>.md` | Markdown report with Mermaid dependency graph |
| `<id>.weavefault.json` | Full JSON snapshot (used for `diff`) |

---

## CLI Reference

### `weavefault generate`

| Option | Default | Description |
|--------|---------|-------------|
| `--diagram` | required | Diagram file (PNG/SVG/drawio/PDF) |
| `--domain` | `cloud` | System domain |
| `--standard` | `IEC_60812` | FMEA standard |
| `--output` | required | Output directory |
| `--format` | `both` | `excel`, `markdown`, or `both` |
| `--provider` | `$LLM_PROVIDER` | LLM provider |
| `--model` | `$LLM_MODEL` | LLM model ID |
| `--verbose` | `false` | Enable debug logging |

### `weavefault diff`

| Option | Default | Description |
|--------|---------|-------------|
| `--before` | required | Earlier `.weavefault.json` snapshot |
| `--after` | required | Later `.weavefault.json` snapshot |
| `--output` | required | Output `.md` diff report path |

### `weavefault watch`

| Option | Default | Description |
|--------|---------|-------------|
| `--diagram` | required | Directory to watch |
| `--output` | required | Output directory |
| `--interval` | `2` | Poll interval in seconds |

---

## Domains

| Domain | Use Case |
|--------|----------|
| `cloud` | AWS/GCP/Azure microservices, APIs, databases |
| `embedded` | IoT, automotive ECU, RTOS, firmware |
| `mechanical` | CNC, hydraulics, structural, manufacturing |
| `hybrid` | Connected vehicles, smart factories, robotics |

## Standards

| Standard | Domain | High Risk RPN |
|----------|--------|---------------|
| `IEC_60812` | Cloud / Industrial | ≥ 200 |
| `AIAG_FMEA4` | Automotive / Mechanical | ≥ 100 |
| `MIL_STD_1629` | Defense / Aerospace | ≥ 200 |
| `ISO_26262` | Functional Safety | ASIL-based |

---

## Next Steps

- [Architecture](architecture.md) — deep dive into the pipeline
- [Configuration](configuration.md) — all config options explained
- [Contributing](../CONTRIBUTING.md) — how to contribute
