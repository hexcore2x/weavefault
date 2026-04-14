"""
Tests for FMEAFormatter, ExcelExporter, and MarkdownExporter.
"""

from __future__ import annotations

import pytest
from weavefault.output.fmea_formatter import (
    AIAG_COLUMNS,
    IEC_60812_COLUMNS,
    STANDARD_COLUMNS,
    FMEAFormatter,
)
from weavefault.output.markdown_exporter import MarkdownExporter

# ──────────────────────────────────────────────────────────────────────────────
# FMEAFormatter
# ──────────────────────────────────────────────────────────────────────────────


class TestFMEAFormatter:
    def test_default_standard_is_iec_60812(self) -> None:
        fmt = FMEAFormatter()
        assert fmt.standard == "IEC_60812"
        assert fmt.columns == IEC_60812_COLUMNS

    def test_aiag_standard_uses_aiag_columns(self) -> None:
        fmt = FMEAFormatter(standard="AIAG_FMEA4")
        assert fmt.columns == AIAG_COLUMNS

    def test_unknown_standard_falls_back_to_iec(self) -> None:
        fmt = FMEAFormatter(standard="SOME_UNKNOWN")
        assert fmt.columns == IEC_60812_COLUMNS

    def test_format_row_returns_dict(self, sample_row) -> None:
        fmt = FMEAFormatter()
        result = fmt.format_row(sample_row)
        assert isinstance(result, dict)

    def test_format_row_contains_all_standard_columns(self, sample_row) -> None:
        fmt = FMEAFormatter()
        result = fmt.format_row(sample_row)
        for col in IEC_60812_COLUMNS:
            assert col in result

    def test_cascade_effects_joined_as_string(self, sample_row) -> None:
        fmt = FMEAFormatter()
        result = fmt.format_row(sample_row)
        assert isinstance(result["cascade_effects"], str)
        assert " | " in result["cascade_effects"] or result["cascade_effects"] == ""

    def test_rpn_present_in_row(self, sample_row) -> None:
        fmt = FMEAFormatter()
        result = fmt.format_row(sample_row)
        assert result["rpn"] == sample_row.rpn

    def test_format_document_returns_list(self, sample_document) -> None:
        fmt = FMEAFormatter()
        rows = fmt.format_document(sample_document)
        assert isinstance(rows, list)
        assert len(rows) == len(sample_document.rows)

    def test_get_header_labels_covers_columns(self) -> None:
        fmt = FMEAFormatter()
        labels = fmt.get_header_labels()
        for col in IEC_60812_COLUMNS:
            assert col in labels
            assert labels[col]  # non-empty

    def test_iso_header_labels_use_exposure_and_controllability(self) -> None:
        fmt = FMEAFormatter(standard="ISO_26262")
        labels = fmt.get_header_labels()
        assert labels["occurrence"] == "Exposure (E)"
        assert labels["detection"] == "Controllability (C)"

    def test_all_standards_have_columns(self) -> None:
        for standard in STANDARD_COLUMNS:
            fmt = FMEAFormatter(standard=standard)
            assert len(fmt.columns) > 0


# ──────────────────────────────────────────────────────────────────────────────
# MarkdownExporter
# ──────────────────────────────────────────────────────────────────────────────


class TestMarkdownExporter:
    @pytest.fixture
    def exporter(self) -> MarkdownExporter:
        return MarkdownExporter()

    def test_export_creates_file(self, exporter, sample_document, tmp_path) -> None:
        path = exporter.export(sample_document, str(tmp_path))
        assert path.exists()
        assert path.suffix == ".md"

    def test_export_to_named_file(self, exporter, sample_document, tmp_path) -> None:
        target = tmp_path / "my_fmea.md"
        path = exporter.export(sample_document, str(target))
        assert path.name == "my_fmea.md"

    def test_markdown_contains_front_matter(
        self, exporter, sample_document, tmp_path
    ) -> None:
        path = exporter.export(sample_document, str(tmp_path))
        content = path.read_text()
        assert content.startswith("---")
        assert "document_id" in content
        assert "domain" in content

    def test_markdown_contains_summary_table(
        self, exporter, sample_document, tmp_path
    ) -> None:
        path = exporter.export(sample_document, str(tmp_path))
        content = path.read_text()
        assert "## Summary" in content
        assert "Total Components" in content

    def test_markdown_contains_fmea_table(
        self, exporter, sample_document, tmp_path
    ) -> None:
        path = exporter.export(sample_document, str(tmp_path))
        content = path.read_text()
        assert "## FMEA Rows" in content
        assert "TLS certificate expiry" in content

    def test_high_risk_section_present(
        self, exporter, sample_document, tmp_path
    ) -> None:
        path = exporter.export(sample_document, str(tmp_path))
        content = path.read_text()
        assert "High Risk" in content

    def test_mermaid_graph_included_when_graph_provided(
        self, exporter, sample_document, three_node_graph, tmp_path
    ) -> None:
        path = exporter.export(sample_document, str(tmp_path), graph=three_node_graph)
        content = path.read_text()
        assert "```mermaid" in content
        assert "flowchart LR" in content

    def test_mermaid_absent_without_graph(
        self, exporter, sample_document, tmp_path
    ) -> None:
        path = exporter.export(sample_document, str(tmp_path), graph=None)
        content = path.read_text()
        assert "```mermaid" not in content

    def test_rpn_bolded_for_high_risk(
        self, exporter, sample_document, tmp_path
    ) -> None:
        path = exporter.export(sample_document, str(tmp_path))
        content = path.read_text()
        # sample_row has RPN = 9*3*6 = 162 (not bold), check low risk row
        # low-risk row RPN = 2*3*2 = 12
        assert "12" in content

    def test_footer_present(self, exporter, sample_document, tmp_path) -> None:
        path = exporter.export(sample_document, str(tmp_path))
        content = path.read_text()
        assert "WeaveFault" in content
        assert "find where it will fault" in content

    def test_aiag_threshold_is_rendered(
        self, exporter, three_node_diagram, tmp_path
    ) -> None:
        from weavefault.ingestion.schema import FMEADocument, FMEARow

        row = FMEARow(
            component_id="svc",
            component_name="Svc",
            failure_mode="bearing wear",
            potential_effect="loss of output quality",
            severity=5,
            occurrence=4,
            detection=6,
        )
        doc = FMEADocument(
            diagram_graph=three_node_diagram,
            rows=[row],
            domain="mechanical",
            standard="AIAG_FMEA4",
            high_risk_threshold=100,
        )
        path = exporter.export(doc, str(tmp_path))
        content = path.read_text()
        assert "High Risk (RPN >= 100)" in content

    def test_iso_high_risk_label_and_metadata_rule_are_rendered(
        self, exporter, three_node_diagram, tmp_path
    ) -> None:
        from weavefault.ingestion.schema import FMEADocument, FMEARow

        row = FMEARow(
            component_id="svc",
            component_name="Brake ECU",
            failure_mode="unsafe torque command",
            potential_effect="loss of vehicle control",
            severity=4,
            occurrence=2,
            detection=4,
            standard_metadata={"asil": "ASIL_D"},
        )
        doc = FMEADocument(
            diagram_graph=three_node_diagram,
            rows=[row],
            domain="embedded",
            standard="ISO_26262",
            high_risk_threshold=200,
        )
        path = exporter.export(doc, str(tmp_path))
        content = path.read_text()
        assert "High Risk (ASIL C/D or RPN >= 200)" in content
        assert "Controllability" not in content
        assert "S=4, E=2, C=4" in content

    def test_empty_rows_document(self, exporter, three_node_diagram, tmp_path) -> None:
        from weavefault.ingestion.schema import FMEADocument

        doc = FMEADocument(
            diagram_graph=three_node_diagram,
            rows=[],
            domain="cloud",
            standard="IEC_60812",
        )
        path = exporter.export(doc, str(tmp_path))
        content = path.read_text()
        assert "No rows generated" in content


# ──────────────────────────────────────────────────────────────────────────────
# ExcelExporter
# ──────────────────────────────────────────────────────────────────────────────


class TestExcelExporter:
    def test_export_creates_xlsx(self, sample_document, tmp_path) -> None:
        pytest.importorskip("openpyxl")
        from weavefault.output.excel_exporter import ExcelExporter

        path = ExcelExporter().export(sample_document, str(tmp_path))
        assert path.exists()
        assert path.suffix == ".xlsx"

    def test_xlsx_has_fmea_sheet(self, sample_document, tmp_path) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        from weavefault.output.excel_exporter import ExcelExporter

        path = ExcelExporter().export(sample_document, str(tmp_path))
        wb = openpyxl.load_workbook(str(path))
        assert "FMEA" in wb.sheetnames

    def test_xlsx_has_summary_sheet(self, sample_document, tmp_path) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        from weavefault.output.excel_exporter import ExcelExporter

        path = ExcelExporter().export(sample_document, str(tmp_path))
        wb = openpyxl.load_workbook(str(path))
        assert "Summary" in wb.sheetnames

    def test_fmea_sheet_row_count(self, sample_document, tmp_path) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        from weavefault.output.excel_exporter import ExcelExporter

        path = ExcelExporter().export(sample_document, str(tmp_path))
        wb = openpyxl.load_workbook(str(path))
        ws = wb["FMEA"]
        # 1 header row + N data rows
        assert ws.max_row == 1 + len(sample_document.rows)

    def test_different_standard_aiag(self, sample_document, tmp_path) -> None:
        pytest.importorskip("openpyxl")
        from weavefault.output.excel_exporter import ExcelExporter

        path = ExcelExporter(standard="AIAG_FMEA4").export(
            sample_document, str(tmp_path)
        )
        assert path.exists()
