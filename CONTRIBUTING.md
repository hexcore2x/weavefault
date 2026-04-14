# Contributing to WeaveFault

Thank you for taking the time to contribute!

---

## Getting Started

### 1. Fork and clone

```bash
git clone https://github.com/YOUR_USERNAME/weavefault.git
cd weavefault
```

### 2. Set up your environment

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
make install-dev
```

### 3. Install pre-commit hooks

```bash
make pre-commit-install
```

### 4. Verify setup

```bash
make test        # run tests
make sample      # generate sample FMEA (no API key needed)
```

---

## Development Workflow

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```

2. Make your changes and write tests.

3. Run the full check suite:
   ```bash
   make fmt        # auto-format
   make lint       # lint check
   make test-cov   # tests + coverage
   ```

4. Commit with a conventional commit message:
   ```
   feat: add support for YAML diagram format
   fix: handle empty component list in GraphBuilder
   docs: update quickstart with watch mode example
   test: add coverage for CriticalityAnalyzer SPOF bonus
   refactor: extract LLM call into shared helper
   ```

5. Push and open a pull request against `main`.

---

## Project Structure

```
src/weavefault/       Core package (ingestion, graph, reasoning, output, cli)
tests/                Unit + integration tests
config/               domains.yaml, standards.yaml
scripts/              setup_rag.py, generate_sample.py
docs/                 architecture.md, quickstart.md, configuration.md
.github/workflows/    CI/CD pipeline
```

See [docs/architecture.md](docs/architecture.md) for a full package map and pipeline walkthrough.

---

## Writing Tests

- All tests live in `tests/`.
- Use `tests/conftest.py` fixtures for shared diagram and graph setup.
- Tests that require LLM API calls should be skipped or mocked:

  ```python
  def test_something(monkeypatch) -> None:
      monkeypatch.setattr(
          "weavefault.reasoning.fmea_generator.FMEAGenerator._call_llm",
          lambda self, prompt: '[]',
      )
  ```

- Tests that require `chromadb` should use `pytest.importorskip("chromadb")`.
- Tests that require `openpyxl` should use `pytest.importorskip("openpyxl")`.

### Test naming

```
tests/test_<module>.py
class Test<ClassName>:
    def test_<scenario>(self, ...) -> None:
```

---

## Code Style

- **Formatter:** `black` (line length 88)
- **Linter:** `ruff` (E, F, I rules)
- **Type hints:** required on all new public functions
- **Docstrings:** Google style, required on all public classes and methods
- **Imports:** lazy imports inside methods for heavy optional dependencies (`cairosvg`, `fitz`, `chromadb`, `anthropic`, `openai`)

---

## Adding a New Domain

1. Add an entry to `config/domains.yaml` following the existing format.
2. Add a corresponding `standards_preference` key.
3. Update `config/standards.yaml` if a new standard is needed.
4. Add a test in `tests/test_diagram_parser.py` or a new test file.

---

## Adding a New Output Format

1. Create `src/weavefault/output/<format>_exporter.py`.
2. Implement an `export(doc: FMEADocument, output_path: str) -> Path` method.
3. Add the format option to `cli/main.py` generate command's `--format` choice.
4. Add tests in `tests/test_formatters.py`.

---

## Commit Message Convention

WeaveFault uses [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use |
|--------|-----|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation only |
| `test:` | Adding or fixing tests |
| `refactor:` | Code change that doesn't fix a bug or add a feature |
| `chore:` | Build, config, dependency changes |
| `perf:` | Performance improvement |

Breaking changes: append `!` after the prefix, e.g. `feat!: rename generate to run`.

---

## Pull Request Checklist

- [ ] Tests added or updated for all changed behaviour
- [ ] `make fmt && make lint` passes with no errors
- [ ] `make test-cov` passes with coverage ≥ 70%
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] Docstrings updated for any changed public API
- [ ] No API keys or secrets committed

---

## Reporting Issues

Please open a GitHub issue with:
- WeaveFault version (`weavefault --version`)
- Python version
- Operating system
- Minimal reproduction steps
- Full error traceback
