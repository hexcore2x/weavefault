"""
CLI integration tests using Click's test runner.
Tests the weavefault generate / diff / watch commands without LLM API calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from weavefault.cli.main import cli, diff, generate
from weavefault.ingestion.diagram_parser import DiagramParseError


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ──────────────────────────────────────────────────────────────────────────────
# weavefault --version / --help
# ──────────────────────────────────────────────────────────────────────────────


class TestTopLevel:
    def test_version_flag(self, runner) -> None:
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help_shows_commands(self, runner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "generate" in result.output
        assert "diff" in result.output
        assert "watch" in result.output

    def test_generate_help(self, runner) -> None:
        result = runner.invoke(cli, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--diagram" in result.output
        assert "--domain" in result.output
        assert "--standard" in result.output

    def test_diff_help(self, runner) -> None:
        result = runner.invoke(cli, ["diff", "--help"])
        assert result.exit_code == 0
        assert "--before" in result.output
        assert "--after" in result.output

    def test_watch_help(self, runner) -> None:
        result = runner.invoke(cli, ["watch", "--help"])
        assert result.exit_code == 0
        assert "--diagram" in result.output
        assert "--output" in result.output


# ──────────────────────────────────────────────────────────────────────────────
# weavefault generate — missing required args
# ──────────────────────────────────────────────────────────────────────────────


class TestGenerateMissingArgs:
    def test_missing_diagram_exits_nonzero(self, runner) -> None:
        result = runner.invoke(generate, ["--output", "/tmp/out"])
        assert result.exit_code != 0

    def test_missing_output_exits_nonzero(self, runner, tmp_path) -> None:
        png = tmp_path / "test.png"
        png.write_bytes(b"fake")
        result = runner.invoke(generate, ["--diagram", str(png)])
        assert result.exit_code != 0

    def test_nonexistent_diagram_exits_nonzero(self, runner, tmp_path) -> None:
        result = runner.invoke(
            generate,
            [
                "--diagram",
                str(tmp_path / "missing.png"),
                "--output",
                str(tmp_path),
            ],
        )
        assert result.exit_code != 0

    def test_parse_failure_exits_nonzero(self, runner, tmp_path, monkeypatch) -> None:
        png = tmp_path / "test.png"
        png.write_bytes(b"fake")

        def _raise_parse_error(self, _path: str):
            raise DiagramParseError("parse failed")

        monkeypatch.setattr(
            "weavefault.ingestion.diagram_parser.DiagramParser.parse",
            _raise_parse_error,
        )
        result = runner.invoke(
            generate,
            ["--diagram", str(png), "--output", str(tmp_path)],
        )
        assert result.exit_code != 0
        assert "parse failed" in result.output


# ──────────────────────────────────────────────────────────────────────────────
# weavefault diff — valid inputs
# ──────────────────────────────────────────────────────────────────────────────


class TestDiffCommand:
    def _make_snapshot(self, path: Path, failure_mode: str = "crash") -> Path:
        """Write a minimal .weavefault.json snapshot to disk."""
        from weavefault.ingestion.schema import (
            Component,
            ComponentType,
            DiagramGraph,
            FMEADocument,
            FMEARow,
        )

        diagram = DiagramGraph(
            components=[
                Component(id="svc", name="Svc", component_type=ComponentType.SERVICE)
            ],
            edges=[],
            domain="cloud",
            confidence=1.0,
        )
        row = FMEARow(
            component_id="svc",
            component_name="Svc",
            failure_mode=failure_mode,
            potential_effect="outage",
            severity=5,
            occurrence=3,
            detection=4,
        )
        doc = FMEADocument(
            diagram_graph=diagram,
            rows=[row],
            domain="cloud",
            standard="IEC_60812",
        )
        snap = path / f"{doc.id}.weavefault.json"
        with open(snap, "w") as f:
            json.dump(doc.to_dict(), f, default=str)
        return snap

    def test_diff_identical_produces_no_changes(self, runner, tmp_path) -> None:
        snap = self._make_snapshot(tmp_path, "crash")
        out = tmp_path / "diff.md"
        result = runner.invoke(
            diff,
            [
                "--before",
                str(snap),
                "--after",
                str(snap),
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "No changes detected" in content

    def test_diff_detects_new_failure_mode(self, runner, tmp_path) -> None:
        (tmp_path / "a").mkdir(parents=True, exist_ok=True)
        (tmp_path / "b").mkdir(parents=True, exist_ok=True)
        before = self._make_snapshot(tmp_path / "a", "crash")
        after = self._make_snapshot(tmp_path / "b", "memory leak")
        out = tmp_path / "diff.md"
        result = runner.invoke(
            diff,
            [
                "--before",
                str(before),
                "--after",
                str(after),
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0
        content = out.read_text(encoding="utf-8")
        assert "New Failure Modes" in content or "Removed Failure Modes" in content

    def test_diff_missing_before_exits_nonzero(self, runner, tmp_path) -> None:
        snap = self._make_snapshot(tmp_path, "crash")
        result = runner.invoke(
            diff,
            [
                "--before",
                str(tmp_path / "missing.json"),
                "--after",
                str(snap),
                "--output",
                str(tmp_path / "out.md"),
            ],
        )
        assert result.exit_code != 0


# ──────────────────────────────────────────────────────────────────────────────
# weavefault generate — format choice validation
# ──────────────────────────────────────────────────────────────────────────────


class TestGenerateFormatChoice:
    def test_invalid_format_exits_nonzero(self, runner, tmp_path) -> None:
        png = tmp_path / "test.png"
        png.write_bytes(b"fake")
        result = runner.invoke(
            generate,
            [
                "--diagram",
                str(png),
                "--output",
                str(tmp_path),
                "--format",
                "invalid_format",
            ],
        )
        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "error" in result.output.lower()
