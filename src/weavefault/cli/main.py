"""
WeaveFault CLI - weavefault generate / diff / watch.

Entry point: weavefault.cli.main:cli
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from weavefault.ingestion.diagram_parser import DiagramParseError
from weavefault.standards import (
    build_high_risk_label,
    canonical_standard_name,
    load_standard_profile,
)

console = Console()
logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "config"


def _get_env(key: str, default: str = "") -> str:
    """Read an environment variable, falling back to .env if loaded."""
    return os.environ.get(key, default)


def _load_dotenv() -> None:
    """Load .env file if present."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file, returning an empty dict if not found or unavailable."""
    if not path.exists():
        return {}
    try:
        import yaml

        with open(path, encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except ImportError:
        logger.debug("PyYAML not installed - skipping config load from %s", path)
        return {}
    except Exception as exc:
        logger.warning("Failed to load %s: %s", path, exc)
        return {}


def _load_domain_context(domain: str, config_dir: Path) -> str:
    """Load domain-specific context for prompt injection."""
    domains = _load_yaml(config_dir / "domains.yaml")
    if domain not in domains:
        return ""

    entry = domains[domain]
    parts: list[str] = [f"Domain: {domain.upper()} - {entry.get('description', '')}"]

    detection_methods = entry.get("detection_methods", [])
    if detection_methods:
        parts.append(f"Common detection methods: {'; '.join(detection_methods[:5])}")

    severity_context = entry.get("severity_context", {})
    if severity_context:
        items = list(severity_context.items())[:2]
        severity_text = "; ".join(f"S{key}: {value}" for key, value in items)
        parts.append(f"Severity context: {severity_text}")

    return " | ".join(parts)


@click.group()
@click.version_option(version="0.1.0", prog_name="weavefault")
def cli() -> None:
    """
    WeaveFault - diagram-native automated FMEA generator.

    We weave through your architecture to find where it will fault.
    """
    _load_dotenv()
    logging.basicConfig(
        level=_get_env("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


@cli.command("generate")
@click.option(
    "--diagram",
    required=True,
    type=click.Path(exists=True),
    help="Path to the architecture diagram (PNG/SVG/drawio/PDF)",
)
@click.option(
    "--domain",
    default="cloud",
    show_default=True,
    help="System domain: cloud | embedded | mechanical | hybrid",
)
@click.option(
    "--standard",
    default="IEC_60812",
    show_default=True,
    help="FMEA standard: IEC_60812 | AIAG | MIL_STD_1629 | ISO_26262",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(),
    help="Output directory for FMEA files",
)
@click.option(
    "--format",
    "fmt",
    default="both",
    show_default=True,
    type=click.Choice(["excel", "markdown", "both"]),
    help="Output format",
)
@click.option(
    "--provider",
    default=None,
    help="LLM provider: anthropic | openai (default: from env)",
)
@click.option(
    "--model",
    default=None,
    help="LLM model ID (default: from env)",
)
@click.option(
    "--config",
    "config_dir",
    default=None,
    type=click.Path(),
    help="Path to config directory (default: auto-detect)",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Enable verbose logging",
)
def generate(
    diagram: str,
    domain: str,
    standard: str,
    output: str,
    fmt: str,
    provider: str | None,
    model: str | None,
    config_dir: str | None,
    verbose: bool,
) -> None:
    """Parse an architecture diagram and generate a full FMEA document."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    cfg_dir = Path(config_dir) if config_dir else _DEFAULT_CONFIG_DIR
    standard = canonical_standard_name(standard)
    standard_profile = load_standard_profile(standard, cfg_dir)
    domain_context = _load_domain_context(domain, cfg_dir)
    if domain_context:
        logger.debug("Domain context loaded: %s", domain_context[:80])

    llm_provider = provider or _get_env("LLM_PROVIDER", "anthropic")
    llm_model = model or _get_env("LLM_MODEL", "claude-opus-4-6")
    vision_model = _get_env("VISION_MODEL", llm_model)
    api_key = (
        _get_env("ANTHROPIC_API_KEY")
        if llm_provider == "anthropic"
        else _get_env("OPENAI_API_KEY")
    )
    chroma_path = _get_env("CHROMA_DB_PATH", "./chroma_db")

    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Parsing diagram...", total=None)

        from weavefault.ingestion.diagram_parser import DiagramParser

        parser = DiagramParser(
            provider=llm_provider,
            vision_model=vision_model,
            api_key=api_key,
        )
        try:
            diagram_graph = parser.parse(diagram)
        except DiagramParseError as exc:
            raise click.ClickException(str(exc)) from exc
        progress.update(
            task,
            description=f"[green]OK parsed {len(diagram_graph.components)} components",
        )

        progress.update(task, description="Building dependency graph...")
        from weavefault.graph.builder import GraphBuilder

        builder = GraphBuilder()
        nx_graph = builder.build(diagram_graph)

        progress.update(task, description="Analysing criticality and SPOFs...")
        from weavefault.graph.criticality import CriticalityAnalyzer

        analyzer = CriticalityAnalyzer()

        progress.update(task, description="Simulating cascade failures...")
        from weavefault.graph.propagation import CascadeSimulator

        simulator = CascadeSimulator()
        cascade_results = simulator.simulate_all(nx_graph)
        criticality = analyzer.analyze(nx_graph, cascade_results)
        analyzer.annotate_graph(nx_graph, criticality)

        from weavefault.reasoning.rag_retriever import RAGRetriever

        rag = RAGRetriever(chroma_db_path=chroma_path)

        progress.update(task, description="Generating FMEA rows (LLM)...")
        from weavefault.reasoning.fmea_generator import FMEAGenerator

        generator = FMEAGenerator(
            provider=llm_provider,
            model=llm_model,
            rag_retriever=rag,
            api_key=api_key,
            config_dir=str(cfg_dir),
        )
        rows = generator.generate(
            diagram=diagram_graph,
            graph=nx_graph,
            cascade_results=cascade_results,
            criticality=criticality,
            domain=domain,
            standard=standard,
        )

        progress.update(task, description="Validating RPN scores...")
        from weavefault.reasoning.rpn_scorer import RPNScorer

        scorer = RPNScorer(
            provider=llm_provider,
            model=llm_model,
            api_key=api_key,
            standard=standard,
            domain=domain,
            config_dir=str(cfg_dir),
        )
        rows = scorer.score_all(rows)

        from weavefault.ingestion.schema import FMEADocument

        doc = FMEADocument(
            diagram_graph=diagram_graph,
            rows=rows,
            domain=domain,
            standard=standard,
            high_risk_threshold=standard_profile.high_risk_threshold,
            model_used=llm_model,
        )

        progress.update(task, description="Exporting FMEA...")
        exported_paths: list[Path] = []

        if fmt in ("excel", "both"):
            from weavefault.output.excel_exporter import ExcelExporter

            xlsx_path = ExcelExporter(standard=standard).export(doc, output)
            exported_paths.append(xlsx_path)

        if fmt in ("markdown", "both"):
            from weavefault.output.markdown_exporter import MarkdownExporter

            md_path = MarkdownExporter().export(doc, output, graph=nx_graph)
            exported_paths.append(md_path)

        doc.save(output)
        exported_paths.append(output_dir / f"{doc.id}.weavefault.json")

        progress.update(task, description="[green]OK done")

    worst = simulator.get_worst_failures(cascade_results, top_n=3)
    _print_generate_summary(doc, exported_paths, worst, domain_context=domain_context)


def _print_generate_summary(
    doc, paths, worst_cascades, domain_context: str = ""
) -> None:
    """Print a Rich summary table after generate completes."""
    standard_profile = load_standard_profile(doc.standard)
    high_risk_label = build_high_risk_label(
        standard_profile,
        doc.high_risk_threshold,
    )

    console.print()
    console.rule("[bold blue]WeaveFault FMEA Complete[/bold blue]")

    table = Table(title="Results", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Total components parsed", str(doc.total_components))
    table.add_row("Failure modes generated", str(len(doc.rows)))
    table.add_row(
        f"High risk items ({high_risk_label})",
        f"[red]{doc.high_risk_count}[/red]",
    )
    table.add_row("Domain", doc.domain)
    table.add_row("Standard", doc.standard)
    if domain_context:
        table.add_row("Domain config", "[green]loaded[/green]")

    console.print(table)

    if worst_cascades:
        console.print()
        console.print("[bold]Top 3 Worst Cascade Failures:[/bold]")
        for i, chain in enumerate(worst_cascades[:3], 1):
            console.print(
                f"  {i}. [yellow]{chain.origin_name}[/yellow] "
                f"-> blast radius [red]{chain.blast_radius_pct:.0f}%[/red] "
                f"({len(chain.affected_nodes)} nodes affected)"
            )

    console.print()
    console.print("[bold]Output files:[/bold]")
    for path in paths:
        console.print(f"  -> {path}")
    console.print()


@cli.command("diff")
@click.option(
    "--before",
    required=True,
    type=click.Path(exists=True),
    help="Path to the earlier FMEA snapshot (.weavefault.json)",
)
@click.option(
    "--after",
    required=True,
    type=click.Path(exists=True),
    help="Path to the later FMEA snapshot (.weavefault.json)",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(),
    help="Output path for the Markdown diff report",
)
def diff(before: str, after: str, output: str) -> None:
    """Compare two FMEA snapshots and produce a diff report."""
    _load_dotenv()

    from weavefault.ingestion.schema import FMEADocument
    from weavefault.output.diff_engine import FMEADiffEngine

    with console.status("Loading FMEA snapshots..."):
        with open(before, encoding="utf-8") as handle:
            before_doc = FMEADocument(**json.load(handle))
        with open(after, encoding="utf-8") as handle:
            after_doc = FMEADocument(**json.load(handle))

    with console.status("Computing diff..."):
        engine = FMEADiffEngine()
        fmea_diff = engine.diff(before_doc, after_doc)
        report = engine.to_markdown(fmea_diff)

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    console.print()
    console.rule("[bold blue]FMEA Diff Complete[/bold blue]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Change Type", style="cyan")
    table.add_column("Count", style="white")
    table.add_row("New failure modes", f"[green]{len(fmea_diff.new_rows)}[/green]")
    table.add_row(
        "Removed failure modes",
        f"[red]{len(fmea_diff.removed_rows)}[/red]",
    )
    table.add_row(
        "Changed failure modes",
        f"[yellow]{len(fmea_diff.changed_rows)}[/yellow]",
    )
    table.add_row("Unchanged", str(fmea_diff.unchanged_count))
    console.print(table)
    console.print(f"\n[bold]Diff report:[/bold] {out_path}")


@cli.command("watch")
@click.option(
    "--diagram",
    required=True,
    type=click.Path(exists=True),
    help="Directory containing diagram files to watch",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(),
    help="Output directory for generated FMEA files",
)
@click.option(
    "--interval",
    default=2,
    show_default=True,
    type=int,
    help="File poll interval in seconds",
)
def watch(diagram: str, output: str, interval: int) -> None:
    """Watch a diagram directory and auto-regenerate FMEA on change."""
    _load_dotenv()
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    watch_dir = Path(diagram).resolve()
    watched_extensions = {
        ".png",
        ".svg",
        ".drawio",
        ".xml",
        ".jpg",
        ".jpeg",
        ".pdf",
    }

    class DiagramChangeHandler(FileSystemEventHandler):
        def on_modified(self, event) -> None:
            if event.is_directory:
                return
            if Path(event.src_path).suffix.lower() in watched_extensions:
                timestamp = time.strftime("%H:%M:%S")
                console.print(
                    f"[{timestamp}] [yellow]diagram changed[/yellow] -> "
                    f"{event.src_path} -> regenerating FMEA..."
                )
                try:
                    from click.testing import CliRunner

                    runner = CliRunner()
                    result = runner.invoke(
                        generate,
                        [
                            "--diagram",
                            event.src_path,
                            "--output",
                            output,
                            "--format",
                            "markdown",
                        ],
                    )
                    if result.exit_code != 0:
                        console.print(f"[red]Generate failed:[/red] {result.output}")
                    else:
                        console.print(
                            f"[{timestamp}] [green]OK FMEA regenerated[/green]"
                        )
                except Exception as exc:
                    console.print(f"[red]Error:[/red] {exc}")

        on_created = on_modified

    observer = Observer()
    observer.schedule(DiagramChangeHandler(), str(watch_dir), recursive=True)
    observer.start()

    console.print(f"[blue]Watching[/blue] {watch_dir} (interval: {interval}s)")
    console.print("Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(interval)
    except KeyboardInterrupt:
        observer.stop()
        console.print("\n[yellow]Stopped.[/yellow]")
    observer.join()


if __name__ == "__main__":
    cli()
