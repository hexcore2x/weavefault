"""
Tests for the file_loader module — get_file_type and validate_file.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from weavefault.ingestion.file_loader import (
    SUPPORTED_EXTENSIONS,
    get_file_type,
    validate_file,
)


class TestGetFileType:
    def test_png_returns_image(self) -> None:
        assert get_file_type("diagram.png") == "image"

    def test_jpg_returns_image(self) -> None:
        assert get_file_type("photo.jpg") == "image"

    def test_jpeg_returns_image(self) -> None:
        assert get_file_type("photo.jpeg") == "image"

    def test_uppercase_extension(self) -> None:
        assert get_file_type("DIAGRAM.PNG") == "image"

    def test_svg_returns_svg(self) -> None:
        assert get_file_type("arch.svg") == "svg"

    def test_drawio_returns_drawio(self) -> None:
        assert get_file_type("flow.drawio") == "drawio"

    def test_xml_returns_drawio(self) -> None:
        assert get_file_type("flow.xml") == "drawio"

    def test_pdf_returns_pdf(self) -> None:
        assert get_file_type("spec.pdf") == "pdf"

    def test_unsupported_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unsupported file type"):
            get_file_type("doc.docx")

    def test_no_extension_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            get_file_type("noextension")

    def test_path_with_directory_works(self) -> None:
        assert get_file_type("/some/dir/arch.svg") == "svg"

    def test_path_with_dots_in_dir(self) -> None:
        assert get_file_type("/my.dir/arch.png") == "image"

    def test_supported_extensions_set_complete(self) -> None:
        expected = {".png", ".jpg", ".jpeg", ".svg", ".drawio", ".xml", ".pdf"}
        assert expected == SUPPORTED_EXTENSIONS


class TestValidateFile:
    def test_existing_file_returns_path(self, tmp_path: Path) -> None:
        f = tmp_path / "test.png"
        f.write_bytes(b"fake png")
        result = validate_file(str(f))
        assert result == f.resolve()

    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            validate_file(str(tmp_path / "missing.png"))

    def test_unsupported_extension_raises_value_error(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello")
        with pytest.raises(ValueError, match="Unsupported file type"):
            validate_file(str(f))

    def test_returns_resolved_path(self, tmp_path: Path) -> None:
        f = tmp_path / "test.svg"
        f.write_text("<svg/>")
        result = validate_file(str(f))
        assert result.is_absolute()
