# WeaveFault — Configuration Reference

## Environment Variables (`.env`)

Copy `.env.example` to `.env` and fill in your values.

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Anthropic API key (required if using Anthropic) |
| `OPENAI_API_KEY` | — | OpenAI API key (required if using OpenAI) |
| `LLM_PROVIDER` | `anthropic` | LLM provider: `anthropic` or `openai` |
| `LLM_MODEL` | `claude-opus-4-6` | Model for FMEA generation and RPN review |
| `VISION_MODEL` | `claude-opus-4-6` | Model for diagram parsing (must support vision) |
| `CHROMA_DB_PATH` | `./chroma_db` | Path to ChromaDB persistence directory |
| `RAG_CHUNK_SIZE` | `512` | Chunk size for RAG document indexing |
| `RAG_OVERLAP` | `64` | Overlap between chunks |
| `LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `WEAVEFAULT_DOMAIN` | `cloud` | Default domain when `--domain` is not passed |
| `WEAVEFAULT_STANDARD` | `IEC_60812` | Default standard when `--standard` is not passed |

---

## config/domains.yaml

Defines domain-specific context injected into FMEA generation prompts.

### Structure

```yaml
<domain_name>:
  description: "Human-readable description"
  example_systems:
    - "Example 1"
  component_types:
    <COMPONENT_TYPE>:
      description: "What this component type means in this domain"
      failure_modes:
        - "Common failure mode 1"
        - "Common failure mode 2"
  severity_context:
    10: "What Severity=10 means in this domain"
    8-9: "..."
  detection_methods:
    - "Detection approach 1"
  standards_preference: "IEC_60812"
```

### Adding a Custom Domain

Add a new top-level key to `config/domains.yaml`:

```yaml
my_domain:
  description: "My custom domain"
  component_types:
    SERVICE:
      failure_modes:
        - "Custom failure mode"
  severity_context:
    10: "Total system loss"
  detection_methods:
    - "My detection method"
  standards_preference: "IEC_60812"
```

Then use it:

```bash
weavefault generate --diagram arch.png --domain my_domain --output ./fmea/
```

---

## config/standards.yaml

Defines RPN thresholds, scoring scales, and standard metadata.

### Structure

```yaml
<STANDARD_ID>:
  full_name: "Full standard name"
  domains: [cloud, embedded, mechanical, hybrid]
  rpn_thresholds:
    high: 200
    medium: 100
    low: 0
  scales:
    severity:
      1: "No effect"
      10: "Catastrophic"
    occurrence:
      1: "Impossible"
      10: "Near certain"
    detection:
      1: "Always detected"
      10: "Never detected"
  notes: "Usage guidance"
```

---

## RAG Corpus (`scripts/setup_rag.py`)

The RAG corpus is a ChromaDB collection of past FMEA examples and standards references.

### Setup

```bash
# Index built-in corpus (14 examples + 4 standards references)
python scripts/setup_rag.py

# Reset and rebuild from scratch
python scripts/setup_rag.py --reset

# Add a custom document
python scripts/setup_rag.py --add ./my_fmea.txt --add-domain cloud

# Use a custom ChromaDB path
python scripts/setup_rag.py --db /opt/weavefault/chroma
```

### Built-in Corpus

| Domain | Examples |
|--------|---------|
| Cloud | API Gateway (TLS, rate limiting), Database (connection pool), Kafka (consumer lag, DLQ), Redis (stampede), Service (OOM) |
| Embedded | Temperature sensor drift, watchdog deadlock, CAN bus error storm |
| Mechanical | Bearing fatigue, hydraulic seal failure |
| Standards | IEC 60812, AIAG FMEA-4, ISO 26262, MIL-STD-1629A reference summaries |

### Adding Custom Documents

```python
from weavefault.reasoning.rag_retriever import RAGRetriever

r = RAGRetriever(chroma_db_path="./chroma_db")
r.add_document(
    content="Your FMEA example text here...",
    doc_id="my_custom_example_001",
    metadata={"domain": "cloud", "component_type": "SERVICE"},
)
```

---

## pyproject.toml

Key configuration sections:

```toml
[project]
requires-python = ">=3.11"

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0", "black>=24.0.0", "ruff>=0.4.0"]

[project.scripts]
weavefault = "weavefault.cli.main:cli"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.black]
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I"]
ignore = ["E501"]
```

---

## Supported Diagram Formats

| Format | Extension | Parser |
|--------|-----------|--------|
| Raster image | `.png`, `.jpg`, `.jpeg` | Vision LLM |
| Vector | `.svg` | cairosvg → PNG → Vision LLM |
| draw.io | `.drawio`, `.xml` | Deterministic XML parse |
| PDF | `.pdf` | PyMuPDF page 1 → PNG → Vision LLM |

---

## Model Recommendations

| Use Case | Recommended Model |
|----------|------------------|
| Best quality FMEA | `claude-opus-4-6` |
| Faster / cheaper | `claude-sonnet-4-6` |
| OpenAI alternative | `gpt-4o` |
| Vision parsing only | Any vision-capable model |
