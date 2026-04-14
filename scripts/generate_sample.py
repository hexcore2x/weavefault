#!/usr/bin/env python3
"""
WeaveFault Sample Generator
============================

Generates a fully synthetic FMEA document from a hard-coded 6-node cloud
architecture — no diagram file or API key required.

Useful for:
  - Verifying a fresh installation
  - CI smoke tests
  - Exploring output format before connecting a real LLM

Usage
-----
    python scripts/generate_sample.py
    python scripts/generate_sample.py --output ./sample_output
    python scripts/generate_sample.py --format markdown
    python scripts/generate_sample.py --format excel
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))


# ──────────────────────────────────────────────────────────────────────────────
# Hard-coded sample architecture: e-commerce checkout platform
# ──────────────────────────────────────────────────────────────────────────────


def build_sample_diagram():
    from weavefault.ingestion.schema import (
        Component,
        ComponentType,
        DiagramGraph,
        Edge,
    )

    components = [
        Component(
            id="api_gateway",
            name="API Gateway",
            component_type=ComponentType.GATEWAY,
            description="NGINX-based ingress — handles TLS termination, rate limiting, routing",
        ),
        Component(
            id="auth_service",
            name="Auth Service",
            component_type=ComponentType.SERVICE,
            description="JWT issue and validation; session management",
        ),
        Component(
            id="order_service",
            name="Order Service",
            component_type=ComponentType.SERVICE,
            description="Checkout and order lifecycle management",
        ),
        Component(
            id="payment_service",
            name="Payment Service",
            component_type=ComponentType.SERVICE,
            description="Payment processing via Stripe/PayPal gateway",
        ),
        Component(
            id="order_db",
            name="Orders Database",
            component_type=ComponentType.DATABASE,
            description="PostgreSQL — primary store for order records",
        ),
        Component(
            id="event_queue",
            name="Event Queue",
            component_type=ComponentType.QUEUE,
            description="Kafka — order events, payment confirmations, notifications",
        ),
    ]

    edges = [
        # fmt: off
        Edge(source_id="api_gateway",    target_id="auth_service",    label="authenticate",  protocol="HTTP"),
        Edge(source_id="api_gateway",    target_id="order_service",   label="checkout",      protocol="HTTP"),
        Edge(source_id="order_service",  target_id="payment_service", label="charge",        protocol="gRPC"),
        Edge(source_id="order_service",  target_id="order_db",        label="persist",       protocol="TCP"),
        Edge(source_id="order_service",  target_id="event_queue",     label="publish",       protocol="TCP"),
        Edge(source_id="payment_service",target_id="event_queue",     label="payment_event", protocol="TCP"),
        # fmt: on
    ]

    return DiagramGraph(
        components=components,
        edges=edges,
        domain="cloud",
        confidence=1.0,
        source_file="sample://ecommerce-checkout",
    )


def build_sample_fmea_rows():
    """Return deterministic sample FMEA rows (no LLM required)."""
    from weavefault.ingestion.schema import FMEARow

    return [
        FMEARow(
            component_id="api_gateway",
            component_name="API Gateway",
            failure_mode="TLS certificate expiry",
            potential_effect="All HTTPS traffic rejected; clients cannot connect",
            cascade_effects=["Auth Service", "Order Service"],
            severity=9,
            occurrence=3,
            detection=6,
            recommended_action="Automate cert rotation with 30-day pre-expiry alert (cert-manager)",
            standard_clause="IEC 60812 Clause 7.4",
            reasoning_chain="Severity=9: all traffic blocked. Occurrence=3: automation reduces frequency. Detection=6: silent until client errors.",
            confidence=0.95,
            generated_by="sample-generator",
        ),
        FMEARow(
            component_id="api_gateway",
            component_name="API Gateway",
            failure_mode="Rate limiter misconfiguration causing false 429s",
            potential_effect="Legitimate users throttled; checkout conversions drop",
            cascade_effects=["Order Service", "Payment Service"],
            severity=7,
            occurrence=4,
            detection=4,
            recommended_action="Test rate limit rules in staging; add Grafana dashboard for 429 rate",
            standard_clause="IEC 60812 Clause 7.3",
            reasoning_chain="Severity=7: revenue impact but not data loss. Detection=4: 429 spike visible in metrics quickly.",
            confidence=0.88,
            generated_by="sample-generator",
        ),
        FMEARow(
            component_id="auth_service",
            component_name="Auth Service",
            failure_mode="JWT signing key rotation failure",
            potential_effect="All new sessions rejected; users cannot log in",
            cascade_effects=["API Gateway", "Order Service", "Payment Service"],
            severity=9,
            occurrence=3,
            detection=5,
            recommended_action="Implement key rotation monitoring; support key overlap period",
            standard_clause="IEC 60812 Clause 7.4",
            reasoning_chain="Severity=9: complete auth failure. Occurrence=3: rotation is infrequent. Detection=5: 401 rate spike detectable.",
            confidence=0.92,
            generated_by="sample-generator",
        ),
        FMEARow(
            component_id="auth_service",
            component_name="Auth Service",
            failure_mode="Memory leak under high concurrent auth requests",
            potential_effect="Service OOM-killed; in-flight auth requests fail",
            cascade_effects=["API Gateway", "Order Service"],
            severity=8,
            occurrence=4,
            detection=5,
            recommended_action="Set container memory limit; add heap profiling; alert on memory trend",
            standard_clause="IEC 60812 Clause 7.4",
            reasoning_chain="Severity=8: auth outage blocks all users. Detection=5: memory metrics visible with lag.",
            confidence=0.85,
            generated_by="sample-generator",
        ),
        FMEARow(
            component_id="order_service",
            component_name="Order Service",
            failure_mode="Partial order commit — payment charged, order not persisted",
            potential_effect="Customer charged with no order record; manual reconciliation required",
            cascade_effects=[
                "Orders Database",
                "Event Queue",
                "Customer Notifications",
            ],
            severity=10,
            occurrence=2,
            detection=5,
            recommended_action="Implement saga/outbox pattern with compensating transactions",
            standard_clause="IEC 60812 Clause 8.2",
            reasoning_chain="Severity=10: financial impact + data inconsistency. Detection=5: reconciliation job can detect but with delay.",
            confidence=0.93,
            generated_by="sample-generator",
        ),
        FMEARow(
            component_id="order_service",
            component_name="Order Service",
            failure_mode="Upstream payment timeout not handled — silent retry storm",
            potential_effect="Duplicate charges on retry; Stripe rate limit hit",
            cascade_effects=["Payment Service", "Event Queue"],
            severity=9,
            occurrence=4,
            detection=6,
            recommended_action="Idempotency keys on all payment calls; circuit breaker on payment client",
            standard_clause="IEC 60812 Clause 7.4",
            reasoning_chain="Severity=9: duplicate charge risk. Occurrence=4: timeouts common at peak. Detection=6: Stripe logs show dupes with delay.",
            confidence=0.90,
            generated_by="sample-generator",
        ),
        FMEARow(
            component_id="payment_service",
            component_name="Payment Service",
            failure_mode="Stripe API version breaking change after dependency update",
            potential_effect="All payment processing fails; checkout completely broken",
            cascade_effects=["Order Service", "Event Queue"],
            severity=10,
            occurrence=2,
            detection=4,
            recommended_action="Pin Stripe SDK version; run contract tests against Stripe sandbox in CI",
            standard_clause="IEC 60812 Clause 7.3",
            reasoning_chain="Severity=10: zero revenue while broken. Occurrence=2: rare but high impact. Detection=4: CI contract tests catch before prod.",
            confidence=0.91,
            generated_by="sample-generator",
        ),
        FMEARow(
            component_id="order_db",
            component_name="Orders Database",
            failure_mode="Connection pool exhaustion during Black Friday traffic spike",
            potential_effect="All order writes fail; 503 errors to customers",
            cascade_effects=["Order Service", "Payment Service"],
            severity=9,
            occurrence=5,
            detection=4,
            recommended_action="Deploy PgBouncer; pre-scale DB instances for peak events; alert at 80% pool",
            standard_clause="IEC 60812 Clause 8.2",
            reasoning_chain="Severity=9: order writes blocked. Occurrence=5: predictable under traffic spikes. Detection=4: pg_stat_activity metrics available.",
            confidence=0.94,
            generated_by="sample-generator",
        ),
        FMEARow(
            component_id="order_db",
            component_name="Orders Database",
            failure_mode="Replication lag causing stale order reads",
            potential_effect="Order status shown as pending after payment confirmed",
            cascade_effects=["Order Service"],
            severity=6,
            occurrence=5,
            detection=5,
            recommended_action="Route status queries to primary; alert on replication lag > 5 seconds",
            standard_clause="IEC 60812 Clause 7.4",
            reasoning_chain="Severity=6: customer confusion but not data loss. Occurrence=5: common under write load.",
            confidence=0.82,
            generated_by="sample-generator",
        ),
        FMEARow(
            component_id="event_queue",
            component_name="Event Queue",
            failure_mode="Consumer group lag accumulation — notification delays",
            potential_effect="Order confirmation emails delayed by hours; customer confusion",
            cascade_effects=["Notification Service", "Audit Logger"],
            severity=6,
            occurrence=5,
            detection=3,
            recommended_action="Alert on consumer lag > 10k messages; auto-scale consumer replicas",
            standard_clause="IEC 60812 Clause 7.3",
            reasoning_chain="Severity=6: delayed notifications, not lost data. Detection=3: Kafka lag metrics are first-class.",
            confidence=0.87,
            generated_by="sample-generator",
        ),
        FMEARow(
            component_id="event_queue",
            component_name="Event Queue",
            failure_mode="Dead-letter queue (DLQ) overflow from persistent poison messages",
            potential_effect="Critical events dropped silently; audit trail incomplete",
            cascade_effects=["Audit Logger", "Compliance Reports"],
            severity=8,
            occurrence=3,
            detection=5,
            recommended_action="Monitor DLQ depth; implement poison message alerting and manual remediation workflow",
            standard_clause="IEC 60812 Clause 8.2",
            reasoning_chain="Severity=8: silent data loss risk in audit trail. Detection=5: DLQ depth metric available.",
            confidence=0.89,
            generated_by="sample-generator",
        ),
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate a sample WeaveFault FMEA document."
    )
    p.add_argument(
        "--output",
        default="./sample_output",
        help="Output directory (default: ./sample_output)",
    )
    p.add_argument(
        "--format",
        choices=["excel", "markdown", "both"],
        default="both",
        help="Export format (default: both)",
    )
    p.add_argument(
        "--standard", default="IEC_60812", help="FMEA standard (default: IEC_60812)"
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("WeaveFault Sample Generator")
    print("=" * 40)

    from weavefault.graph.builder import GraphBuilder
    from weavefault.graph.criticality import CriticalityAnalyzer
    from weavefault.graph.propagation import CascadeSimulator
    from weavefault.ingestion.schema import FMEADocument
    from weavefault.output.excel_exporter import ExcelExporter
    from weavefault.output.markdown_exporter import MarkdownExporter
    from weavefault.standards import canonical_standard_name, load_standard_profile

    standard = canonical_standard_name(args.standard)
    standard_profile = load_standard_profile(standard)

    print("Building sample architecture: E-Commerce Checkout Platform")
    diagram = build_sample_diagram()
    print(f"  Components: {len(diagram.components)}")
    print(f"  Edges:      {len(diagram.edges)}")

    print("Building dependency graph...")
    builder = GraphBuilder()
    nx_graph = builder.build(diagram)

    print("Running cascade simulation...")
    simulator = CascadeSimulator()
    cascade_results = simulator.simulate_all(nx_graph)
    worst = simulator.get_worst_failures(cascade_results, top_n=3)

    print("Analysing criticality and SPOFs...")
    analyzer = CriticalityAnalyzer()
    criticality = analyzer.analyze(nx_graph, cascade_results)
    analyzer.annotate_graph(nx_graph, criticality)

    print("Loading sample FMEA rows (no LLM required)...")
    rows = build_sample_fmea_rows()
    rows.sort(key=lambda r: r.rpn, reverse=True)
    print(f"  {len(rows)} failure modes generated")

    doc = FMEADocument(
        diagram_graph=diagram,
        rows=rows,
        domain="cloud",
        standard=standard,
        high_risk_threshold=standard_profile.high_risk_threshold,
        model_used="sample-generator",
    )

    exported: list[Path] = []
    if args.format in ("excel", "both"):
        path = ExcelExporter(standard=standard).export(doc, args.output)
        exported.append(path)
    if args.format in ("markdown", "both"):
        path = MarkdownExporter().export(doc, args.output, graph=nx_graph)
        exported.append(path)
    doc.save(args.output)
    exported.append(output_dir / f"{doc.id}.weavefault.json")

    print()
    print("=" * 40)
    print(f"Components parsed:          {doc.total_components}")
    print(f"Failure modes:              {len(doc.rows)}")
    print(f"High risk (RPN >= {doc.high_risk_threshold}):     {doc.high_risk_count}")
    print()
    print("Top 3 worst cascade failures:")
    for i, chain in enumerate(worst[:3], 1):
        print(
            f"  {i}. {chain.origin_name} → blast radius {chain.blast_radius_pct:.0f}% ({len(chain.affected_nodes)} nodes)"
        )
    print()
    print("Output files:")
    for p in exported:
        print(f"  → {p}")
    print()
    print("Success! WeaveFault is installed correctly.")


if __name__ == "__main__":
    main()
