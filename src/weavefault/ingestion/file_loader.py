"""
WeaveFault file loader — route input files by extension to the correct parser.
"""
from __future__ import annotations

from pathlib import Path

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".drawio", ".xml", ".pdf"}


def get_file_type(path: str) -> str:
    """
    Determine the diagram file type from its extension.

    Args:
        path: Path to the diagram file.

    Returns:
        One of: 'image', 'svg', 'drawio', 'pdf'

    Raises:
        ValueError: If the file extension is not supported.
    """
    ext = Path(path).suffix.lower()
    if ext in {".png", ".jpg", ".jpeg"}:
        return "image"
    if ext == ".svg":
        return "svg"
    if ext in {".drawio", ".xml"}:
        return "drawio"
    if ext == ".pdf":
        return "pdf"
    raise ValueError(
        f"Unsupported file type: {ext!r}. " f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
    )


def validate_file(path: str) -> Path:
    """
    Validate that the file exists and has a supported extension.

    Args:
        path: Path to the diagram file.

    Returns:
        Resolved Path object.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file extension is not supported.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Diagram file not found: {path!r}")
    get_file_type(str(p))  # validate extension
    return p
