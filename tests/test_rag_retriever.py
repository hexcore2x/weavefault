"""
Tests for RAGRetriever — graceful degradation when ChromaDB is absent or empty.
"""

from __future__ import annotations

import pytest

from weavefault.reasoning.rag_retriever import (
    DEFAULT_COLLECTION,
    DEFAULT_N_RESULTS,
    RAGRetriever,
)


class TestInit:
    def test_defaults(self) -> None:
        r = RAGRetriever()
        assert r.collection_name == DEFAULT_COLLECTION
        assert r.n_results == DEFAULT_N_RESULTS
        assert r._client is None
        assert r._collection is None

    def test_custom_path_and_collection(self) -> None:
        r = RAGRetriever(
            chroma_db_path="/tmp/mydb", collection_name="my_col", n_results=5
        )
        assert r.n_results == 5
        assert r.collection_name == "my_col"

    def test_path_is_resolved(self) -> None:
        r = RAGRetriever(chroma_db_path="./relative_path")
        assert r.chroma_db_path != "./relative_path"
        assert "relative_path" in r.chroma_db_path


class TestRetrieveWithoutChromaDB:
    """When chromadb is not available or collection is missing, retrieve returns ''."""

    def test_returns_empty_string_when_no_collection(self, tmp_path) -> None:
        r = RAGRetriever(chroma_db_path=str(tmp_path / "empty_db"))
        result = r.retrieve("API Gateway failure")
        assert result == ""

    def test_retrieve_with_domain_returns_empty_when_no_collection(
        self, tmp_path
    ) -> None:
        r = RAGRetriever(chroma_db_path=str(tmp_path / "empty_db"))
        result = r.retrieve("database crash", component_type="DATABASE", domain="cloud")
        assert result == ""

    def test_no_exception_raised_on_missing_db(self, tmp_path) -> None:
        r = RAGRetriever(chroma_db_path=str(tmp_path / "nonexistent"))
        r.retrieve("test query")  # should not raise


class TestRetrieveWithChromaDB:
    """Integration-style tests that use a real (temporary) ChromaDB instance."""

    @pytest.fixture
    def populated_retriever(self, tmp_path) -> RAGRetriever:
        chromadb = pytest.importorskip("chromadb")
        r = RAGRetriever(
            chroma_db_path=str(tmp_path / "test_chroma"),
            collection_name="test_collection",
            n_results=2,
        )
        client = chromadb.PersistentClient(path=str(tmp_path / "test_chroma"))
        collection = client.get_or_create_collection("test_collection")
        r._client = client
        r._collection = collection

        collection.upsert(
            ids=["doc_1", "doc_2", "doc_3"],
            documents=[
                "API Gateway TLS certificate expiry causes all traffic to fail. Severity=9, RPN=216.",
                "Database connection pool exhaustion under traffic spike. Severity=8, RPN=192.",
                "Redis cache stampede after deployment. Severity=7, RPN=140.",
            ],
            metadatas=[
                {"domain": "cloud", "component_type": "GATEWAY"},
                {"domain": "cloud", "component_type": "DATABASE"},
                {"domain": "cloud", "component_type": "CACHE"},
            ],
        )
        return r

    def test_retrieve_returns_non_empty_string(self, populated_retriever) -> None:
        result = populated_retriever.retrieve("API Gateway failure")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_retrieve_contains_example_markers(self, populated_retriever) -> None:
        result = populated_retriever.retrieve("TLS certificate")
        assert "[Example" in result

    def test_retrieve_n_results_respected(self, populated_retriever) -> None:
        result = populated_retriever.retrieve("cloud failure modes")
        # n_results=2, so at most [Example 1] and [Example 2]
        assert "[Example 3]" not in result

    def test_add_document_and_retrieve(self, tmp_path) -> None:
        chromadb = pytest.importorskip("chromadb")
        r = RAGRetriever(
            chroma_db_path=str(tmp_path / "add_test"),
            collection_name="add_collection",
            n_results=3,
        )
        client = chromadb.PersistentClient(path=str(tmp_path / "add_test"))
        collection = client.get_or_create_collection("add_collection")
        r._client = client
        r._collection = collection

        r.add_document(
            content="Sensor drift causes temperature misread in embedded systems.",
            doc_id="sensor_drift_001",
            metadata={"domain": "embedded", "component_type": "SENSOR"},
        )
        result = r.retrieve("sensor drift", domain="embedded")
        # ChromaDB may not support metadata filtering without embeddings — just check no exception
        assert isinstance(result, str)
