#!/usr/bin/env python3
"""
WeaveFault RAG Corpus Setup Script
===================================

Indexes the built-in FMEA examples and standards summaries into a ChromaDB
collection so that the FMEAGenerator can retrieve relevant past examples.

Usage
-----
    python scripts/setup_rag.py                     # default ./chroma_db
    python scripts/setup_rag.py --db ./my_chroma    # custom path
    python scripts/setup_rag.py --reset             # drop and rebuild
    python scripts/setup_rag.py --add ./my_fmea.md  # add custom document

The built-in corpus includes:
  - Cloud architecture FMEA examples (gateway, service, database, queue, cache)
  - Embedded firmware FMEA examples (sensor, actuator, RTOS, CAN bus)
  - Mechanical FMEA examples (rotating machinery, hydraulics, structural)
  - Key clauses from IEC 60812, AIAG FMEA-4, MIL-STD-1629, ISO 26262
"""
from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path
from typing import NamedTuple

# ── ensure the package is importable from the repo root ───────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))


# ──────────────────────────────────────────────────────────────────────────────
# Built-in corpus
# ──────────────────────────────────────────────────────────────────────────────


class CorpusEntry(NamedTuple):
    doc_id: str
    domain: str
    standard: str
    component_type: str
    content: str


BUILTIN_CORPUS: list[CorpusEntry] = [
    # ── Cloud ────────────────────────────────────────────────────────────────
    CorpusEntry(
        doc_id="cloud_gateway_tls_expiry",
        domain="cloud",
        standard="IEC_60812",
        component_type="GATEWAY",
        content=textwrap.dedent(
            """\
            Component: API Gateway
            Failure Mode: TLS certificate expiry
            Potential Effect: All HTTPS traffic rejected with ERR_CERT_DATE_INVALID; clients cannot connect.
            Cascade Effects: Auth Service, Frontend, Mobile Clients
            Severity: 9 (full outage for all consumers)
            Occurrence: 4 (happens when cert rotation automation breaks; ~1 per year)
            Detection: 6 (monitoring may not alert until cert expires)
            RPN: 216
            Recommended Action: Implement automated cert rotation (cert-manager) with 30-day pre-expiry alert.
            Standard Clause: IEC 60812 Clause 7.4 — Effect analysis
            Reasoning: Severity=9 because TLS expiry silently drops all traffic.
                       Occurrence=4 because rotation automation reduces frequency but doesn't eliminate human error.
                       Detection=6 because without proactive monitoring the failure manifests to end users first.
        """
        ),
    ),
    CorpusEntry(
        doc_id="cloud_db_connection_pool",
        domain="cloud",
        standard="IEC_60812",
        component_type="DATABASE",
        content=textwrap.dedent(
            """\
            Component: PostgreSQL Database
            Failure Mode: Connection pool exhaustion
            Potential Effect: New DB connections fail; services receive 'too many clients' error.
            Cascade Effects: Auth Service, Order Service, Analytics Service
            Severity: 8 (all write operations blocked)
            Occurrence: 6 (common under sustained traffic spikes without pool limits)
            Detection: 4 (metrics dashboards show connection count; alerts fire before total exhaustion)
            RPN: 192
            Recommended Action: Set max_connections, use PgBouncer connection pooler, alert at 80% pool utilisation.
            Standard Clause: IEC 60812 Clause 8.2 — Criticality analysis
            Reasoning: Severity=8 because writes blocked while reads may still work from replica.
                       Occurrence=6 because traffic spikes without pooler are common.
                       Detection=4 because Prometheus pg_stat_activity metrics give advance warning.
        """
        ),
    ),
    CorpusEntry(
        doc_id="cloud_kafka_consumer_lag",
        domain="cloud",
        standard="IEC_60812",
        component_type="QUEUE",
        content=textwrap.dedent(
            """\
            Component: Kafka Message Broker
            Failure Mode: Consumer group lag accumulation
            Potential Effect: Event processing falls behind; downstream services process stale events.
            Cascade Effects: Notification Service, Audit Logger, Analytics Pipeline
            Severity: 7 (delayed processing; data integrity risk)
            Occurrence: 5 (occurs when consumer is under-provisioned or has processing bugs)
            Detection: 3 (consumer lag is easily monitored via Kafka exporter)
            RPN: 105
            Recommended Action: Set lag alerting thresholds, enable auto-scaling for consumer group, add DLQ.
            Standard Clause: IEC 60812 Clause 7.3 — Failure mode identification
            Reasoning: Severity=7 because lag causes delayed notifications and audit gaps but not data loss.
                       Detection=3 because Kafka consumer lag is a first-class metric.
        """
        ),
    ),
    CorpusEntry(
        doc_id="cloud_cache_stampede",
        domain="cloud",
        standard="IEC_60812",
        component_type="CACHE",
        content=textwrap.dedent(
            """\
            Component: Redis Cache
            Failure Mode: Cache stampede on cold start / mass expiry
            Potential Effect: All requests bypass cache simultaneously; database overwhelmed.
            Cascade Effects: PostgreSQL Database, Auth Service, Product Catalogue
            Severity: 8 (thundering herd can cause DB outage)
            Occurrence: 5 (happens after deployment or mass key expiry)
            Detection: 5 (cache miss rate spike is visible in metrics but reaction time short)
            RPN: 200
            Recommended Action: Implement jittered TTL, probabilistic early expiry (XFetch), Redis replication.
            Standard Clause: IEC 60812 Clause 7.4
            Reasoning: Stampede is a well-known Redis failure mode in cloud architectures.
        """
        ),
    ),
    CorpusEntry(
        doc_id="cloud_service_oom",
        domain="cloud",
        standard="IEC_60812",
        component_type="SERVICE",
        content=textwrap.dedent(
            """\
            Component: Payment Service
            Failure Mode: Memory leak causing OOM kill
            Potential Effect: Pod/container killed by runtime; in-flight transactions may be lost.
            Cascade Effects: Order Service, Ledger Service, Customer Notifications
            Severity: 9 (in-flight payment data at risk)
            Occurrence: 4 (memory leaks surface under sustained load)
            Detection: 5 (memory usage trending up is detectable but often missed without alerting)
            RPN: 180
            Recommended Action: Set container memory limits, add memory usage alerting, heap profiling in CI.
            Standard Clause: IEC 60812 Clause 7.4
            Reasoning: Severity=9 due to financial transaction risk; detection improved with resource alerts.
        """
        ),
    ),
    # ── Embedded ─────────────────────────────────────────────────────────────
    CorpusEntry(
        doc_id="embedded_sensor_drift",
        domain="embedded",
        standard="IEC_60812",
        component_type="SENSOR",
        content=textwrap.dedent(
            """\
            Component: Temperature Sensor (NTC Thermistor)
            Failure Mode: Calibration drift from thermal aging
            Potential Effect: Incorrect temperature reading fed to control loop; over/under-heating.
            Cascade Effects: PID Controller, Safety Cutoff, Heating Actuator
            Severity: 8 (process operates outside safe thermal range)
            Occurrence: 5 (thermistor aging is predictable but time-dependent)
            Detection: 6 (drift is gradual; not detectable without periodic calibration)
            RPN: 240
            Recommended Action: Implement periodic self-calibration routine against known reference; add cross-sensor voting.
            Standard Clause: IEC 60812 Clause 7.4
            Reasoning: High severity because temperature control errors can damage product or equipment.
        """
        ),
    ),
    CorpusEntry(
        doc_id="embedded_watchdog_failure",
        domain="embedded",
        standard="IEC_60812",
        component_type="SERVICE",
        content=textwrap.dedent(
            """\
            Component: Main Firmware Task (RTOS)
            Failure Mode: Watchdog timer not kicked due to deadlock in ISR
            Potential Effect: System hard-reset; actuators may reach fail-safe state or hold last command.
            Cascade Effects: Motor Driver, Display Controller, CAN Bus
            Severity: 7 (uncontrolled reset during operation)
            Occurrence: 3 (deadlock requires specific race condition)
            Detection: 4 (watchdog itself detects and resets; event logged in NVRAM)
            RPN: 84
            Recommended Action: Use independent hardware watchdog, log reset cause to NVRAM, review ISR locking.
            Standard Clause: IEC 60812 Clause 7.3
            Reasoning: Detection=4 because the watchdog catches the failure but the root cause (deadlock) is hard to reproduce.
        """
        ),
    ),
    CorpusEntry(
        doc_id="embedded_can_error_storm",
        domain="embedded",
        standard="IEC_60812",
        component_type="NETWORK",
        content=textwrap.dedent(
            """\
            Component: CAN Bus
            Failure Mode: Error frame storm from faulty node entering bus-off state
            Potential Effect: All CAN traffic disrupted; other nodes miss critical messages.
            Cascade Effects: ECU Cluster, Dashboard, Safety Controller
            Severity: 9 (safety-critical CAN messages (e.g. braking commands) may be lost)
            Occurrence: 3 (requires hardware fault in one node)
            Detection: 5 (CAN error counter registers detectable but requires active monitoring)
            RPN: 135
            Recommended Action: Implement CAN bus-off recovery with node isolation; add CAN traffic monitor.
            Standard Clause: IEC 60812 Clause 8.3
            Reasoning: Severity=9 because braking or steering CAN messages may be missed in error storm.
        """
        ),
    ),
    # ── Mechanical ───────────────────────────────────────────────────────────
    CorpusEntry(
        doc_id="mechanical_bearing_fatigue",
        domain="mechanical",
        standard="AIAG_FMEA4",
        component_type="SERVICE",
        content=textwrap.dedent(
            """\
            Component: Spindle Bearing Assembly
            Failure Mode: Rolling element fatigue spalling
            Potential Effect: Vibration spike; spindle runout exceeds tolerance; machined parts scrapped.
            Cascade Effects: Drive Shaft, Machine Frame, Workpiece
            Severity: 7 (machining quality loss, potential spindle damage)
            Occurrence: 4 (predictable fatigue life; depends on lubrication and load)
            Detection: 4 (vibration analysis and oil debris monitoring detects early)
            RPN: 112
            Recommended Action: Implement vibration-based CBM; replace bearings at 80% of L10 life.
            Standard Clause: AIAG FMEA-4 Section 5
            Reasoning: Early detection via FFT vibration analysis reduces detection score; preventive replacement reduces occurrence.
        """
        ),
    ),
    CorpusEntry(
        doc_id="mechanical_hydraulic_seal",
        domain="mechanical",
        standard="AIAG_FMEA4",
        component_type="ACTUATOR",
        content=textwrap.dedent(
            """\
            Component: Hydraulic Cylinder
            Failure Mode: Dynamic seal failure (rod seal leakage)
            Potential Effect: Hydraulic fluid loss; reduced actuator force; fire risk near hot surfaces.
            Cascade Effects: Clamping System, Coolant Circuit, Machine Frame
            Severity: 8 (fire risk and loss of clamping force)
            Occurrence: 5 (seal life is pressure and temperature dependent)
            Detection: 5 (visible leakage detectable by operator; may not be noticed immediately)
            RPN: 200
            Recommended Action: Scheduled seal replacement per OEM intervals; install leak detection sensors.
            Standard Clause: AIAG FMEA-4 Section 5
            Reasoning: Severity=8 due to fire risk from hydraulic fluid near hot machine surfaces.
        """
        ),
    ),
    # ── Standards Reference ───────────────────────────────────────────────────
    CorpusEntry(
        doc_id="ref_iec_60812_rpn",
        domain="cloud",
        standard="IEC_60812",
        component_type="UNKNOWN",
        content=textwrap.dedent(
            """\
            IEC 60812:2018 — RPN Guidance
            RPN = Severity × Occurrence × Detection (each 1–10).
            High risk threshold: RPN ≥ 200.
            Medium risk: 100 ≤ RPN < 200.
            Low risk: RPN < 100.
            Severity 9–10 items require action regardless of RPN.
            Clause 7.4 requires each effect to be traced to potential causes.
            Clause 8.2 requires criticality ranking when resources are limited.
            Clause 9 requires recommended actions for all high-risk items.
        """
        ),
    ),
    CorpusEntry(
        doc_id="ref_aiag_fmea4_rpn",
        domain="mechanical",
        standard="AIAG_FMEA4",
        component_type="UNKNOWN",
        content=textwrap.dedent(
            """\
            AIAG FMEA-4 — RPN Guidance
            RPN = Severity × Occurrence × Detection (each 1–10).
            High risk threshold: RPN ≥ 100.
            Severity = 9 or 10 always requires design action regardless of RPN.
            Section 3: Functional block diagram required before FMEA.
            Section 5: Each failure mode must have at least one recommended action.
            Section 6: Action results must update RPN after countermeasure implementation.
        """
        ),
    ),
    CorpusEntry(
        doc_id="ref_iso_26262_asil",
        domain="embedded",
        standard="ISO_26262",
        component_type="UNKNOWN",
        content=textwrap.dedent(
            """\
            ISO 26262:2018 — ASIL Determination
            ASIL is determined by: Severity (S0–S3) × Exposure (E0–E4) × Controllability (C0–C3).
            ASIL D: highest integrity level — requires full hardware and software safety measures.
            ASIL C: requires independence between safety and non-safety partitions.
            ASIL B: requires hardware diagnostic coverage > 60%.
            ASIL A: basic safety measures required.
            QM: quality management only — no specific safety standard requirement.
            Part 4 (System level): hazard analysis and risk assessment (HARA).
            Part 5 (Hardware): hardware architecture metrics (SPFM, LFM).
            Part 6 (Software): software safety requirements, MISRA C compliance.
        """
        ),
    ),
    CorpusEntry(
        doc_id="ref_mil_std_1629a",
        domain="embedded",
        standard="MIL_STD_1629",
        component_type="UNKNOWN",
        content=textwrap.dedent(
            """\
            MIL-STD-1629A — Criticality Analysis
            Criticality Number (Cm) = β × α × λp × t
              β = conditional probability failure mode causes mission loss
              α = failure mode ratio
              λp = part failure rate (per hour, from MIL-HDBK-217)
              t = mission time (hours)
            Criticality Matrix: plots Severity Category (I–IV) vs Criticality Number.
            Category I (Catastrophic) items require redundancy or elimination.
            Category II (Critical) items require detection and mitigation.
            Worksheet 101: FMEA worksheet.
            Worksheet 102: Criticality analysis worksheet.
        """
        ),
    ),
]


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set up WeaveFault RAG corpus in ChromaDB."
    )
    parser.add_argument(
        "--db",
        default="./chroma_db",
        help="Path to ChromaDB persistence directory (default: ./chroma_db)",
    )
    parser.add_argument(
        "--collection",
        default="weavefault_fmea_corpus",
        help="ChromaDB collection name",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and rebuild the collection from scratch",
    )
    parser.add_argument(
        "--add",
        metavar="FILE",
        help="Add a custom plain-text document to the corpus",
    )
    parser.add_argument(
        "--add-id",
        metavar="ID",
        default=None,
        help="Document ID for --add (default: filename stem)",
    )
    parser.add_argument(
        "--add-domain",
        metavar="DOMAIN",
        default="cloud",
        help="Domain tag for --add (default: cloud)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        import chromadb as cdb
    except ImportError:
        print("ERROR: chromadb is not installed. Run: pip install chromadb")
        sys.exit(1)

    from weavefault.reasoning.rag_retriever import RAGRetriever

    retriever = RAGRetriever(
        chroma_db_path=args.db,
        collection_name=args.collection,
    )

    client = cdb.PersistentClient(path=str(Path(args.db).resolve()))

    if args.reset:
        try:
            client.delete_collection(args.collection)
            print(f"Dropped existing collection: {args.collection!r}")
        except Exception:
            pass

    collection = client.get_or_create_collection(name=args.collection)
    retriever._client = client
    retriever._collection = collection

    # Index built-in corpus
    print(f"Indexing {len(BUILTIN_CORPUS)} built-in corpus entries...")
    for i, entry in enumerate(BUILTIN_CORPUS, 1):
        collection.upsert(
            ids=[entry.doc_id],
            documents=[entry.content],
            metadatas=[
                {
                    "domain": entry.domain,
                    "standard": entry.standard,
                    "component_type": entry.component_type,
                }
            ],
        )
        print(f"  [{i:02d}/{len(BUILTIN_CORPUS)}] {entry.doc_id}")

    # Add custom document if requested
    if args.add:
        custom_path = Path(args.add)
        if not custom_path.exists():
            print(f"ERROR: File not found: {args.add}")
            sys.exit(1)
        doc_id = args.add_id or custom_path.stem
        content = custom_path.read_text(encoding="utf-8")
        collection.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[{"domain": args.add_domain, "standard": "custom"}],
        )
        print(f"Added custom document: {doc_id!r}")

    count = collection.count()
    print(f"\nRAG corpus ready: {count} documents in {args.db!r} / {args.collection!r}")
    print("Run `weavefault generate` to use the RAG corpus.")


if __name__ == "__main__":
    main()
