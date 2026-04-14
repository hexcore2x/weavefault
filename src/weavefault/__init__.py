"""
WeaveFault — Diagram-native automated FMEA generator powered by LLMs.

"We weave through your architecture to find where it will fault."
"""
from __future__ import annotations

__version__ = "0.1.0"
__author__ = "WeaveFault"
__description__ = "We weave through your architecture to find where it will fault."

from weavefault.ingestion.schema import DiagramGraph, FMEADocument, FMEARow

__all__ = [
    "__version__",
    "__author__",
    "__description__",
    "DiagramGraph",
    "FMEADocument",
    "FMEARow",
]
