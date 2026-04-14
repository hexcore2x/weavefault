# ──────────────────────────────────────────────────────────────────────────────
# WeaveFault — Developer Makefile
# ──────────────────────────────────────────────────────────────────────────────
.PHONY: help install install-dev lint fmt fmt-check test test-cov \
        sample rag-setup clean build dist pre-commit-install

PYTHON   ?= python
PIP      ?= pip
SRC      := src tests scripts
VENV     := .venv

# Default target
help:
	@echo ""
	@echo "WeaveFault — available targets"
	@echo "────────────────────────────────────────────────"
	@echo "  make install           Install package (editable)"
	@echo "  make install-dev       Install with dev dependencies"
	@echo "  make lint              Run ruff linter"
	@echo "  make fmt               Auto-format with black"
	@echo "  make fmt-check         Check formatting without modifying"
	@echo "  make test              Run test suite"
	@echo "  make test-cov          Run tests + coverage report"
	@echo "  make sample            Generate a sample FMEA (no API key)"
	@echo "  make rag-setup         Index built-in corpus into ChromaDB"
	@echo "  make build             Build wheel and sdist"
	@echo "  make clean             Remove build artifacts and cache"
	@echo "  make pre-commit-install Install pre-commit hooks"
	@echo "────────────────────────────────────────────────"
	@echo ""

# ── Installation ──────────────────────────────────────────────────────────────
install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"
	$(PIP) install networkx pydantic pydantic-settings click rich openpyxl \
	               cairosvg PyMuPDF chromadb watchdog python-dotenv jinja2 \
	               pytest-cov

# ── Code quality ──────────────────────────────────────────────────────────────
lint:
	ruff check $(SRC)

fmt:
	black $(SRC)

fmt-check:
	black --check --diff $(SRC)

# ── Testing ───────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ \
	  --cov=weavefault \
	  --cov-report=term-missing \
	  --cov-report=html:htmlcov \
	  --cov-fail-under=70 \
	  -v
	@echo "Coverage HTML report: htmlcov/index.html"

# ── Scripts ───────────────────────────────────────────────────────────────────
sample:
	$(PYTHON) scripts/generate_sample.py --output ./sample_output --format both
	@echo "Sample output written to ./sample_output/"

rag-setup:
	$(PYTHON) scripts/setup_rag.py --db ./chroma_db
	@echo "RAG corpus ready in ./chroma_db"

rag-reset:
	$(PYTHON) scripts/setup_rag.py --db ./chroma_db --reset

# ── Build ─────────────────────────────────────────────────────────────────────
build:
	$(PIP) install build
	$(PYTHON) -m build

dist: build

# ── Hooks ─────────────────────────────────────────────────────────────────────
pre-commit-install:
	$(PIP) install pre-commit
	pre-commit install
	@echo "Pre-commit hooks installed."

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".coverage" -delete 2>/dev/null || true
	rm -rf dist/ build/
	@echo "Cleaned."
