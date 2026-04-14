"""
WeaveFault RAGRetriever — semantic retrieval over past FMEAs and standards.

Uses ChromaDB as the vector store and sentence-transformers (or the LLM
provider's embedding API) for embedding.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "weavefault_fmea_corpus"
DEFAULT_N_RESULTS = 3


class RAGRetriever:
    """
    Retrieve relevant FMEA examples and standard clauses from a ChromaDB store.

    The corpus is populated by running `scripts/setup_rag.py`.
    If the collection does not exist, retrieval returns an empty context
    rather than failing the generation pipeline.
    """

    def __init__(
        self,
        chroma_db_path: str = "./chroma_db",
        collection_name: str = DEFAULT_COLLECTION,
        n_results: int = DEFAULT_N_RESULTS,
    ) -> None:
        """
        Initialise the RAGRetriever.

        Args:
            chroma_db_path: Path to the ChromaDB persistence directory.
            collection_name: Name of the ChromaDB collection.
            n_results: Number of results to return per query.
        """
        self.chroma_db_path = str(Path(chroma_db_path).resolve())
        self.collection_name = collection_name
        self.n_results = n_results
        self._client = None
        self._collection = None

    def _get_collection(self):
        """Lazily initialise the ChromaDB client and collection."""
        if self._collection is not None:
            return self._collection

        try:
            import chromadb  # lazy import

            self._client = chromadb.PersistentClient(path=self.chroma_db_path)
            try:
                self._collection = self._client.get_collection(
                    name=self.collection_name
                )
                logger.info(
                    "RAG: loaded collection %r from %s",
                    self.collection_name,
                    self.chroma_db_path,
                )
            except Exception:
                logger.warning(
                    "RAG collection %r not found — run scripts/setup_rag.py to index standards",
                    self.collection_name,
                )
                self._collection = None
        except ImportError:
            logger.warning("chromadb not installed — RAG disabled")

        return self._collection

    def retrieve(
        self,
        query: str,
        component_type: str = "",
        domain: str = "cloud",
    ) -> str:
        """
        Retrieve relevant context for an FMEA generation query.

        Args:
            query: Natural language query (e.g. component name + failure mode).
            component_type: Optional component type to narrow results.
            domain: System domain for filtering.

        Returns:
            Formatted string of retrieved context, or empty string if unavailable.
        """
        collection = self._get_collection()
        if collection is None:
            return ""

        try:
            where: dict = {}
            if domain:
                where["domain"] = domain

            results = collection.query(
                query_texts=[query],
                n_results=self.n_results,
                where=where if where else None,
            )

            documents = results.get("documents", [[]])[0]
            if not documents:
                return ""

            context_parts = []
            for i, doc in enumerate(documents, 1):
                context_parts.append(f"[Example {i}]\n{doc}")

            return "\n\n".join(context_parts)

        except Exception as exc:
            logger.warning("RAG query failed: %s", exc)
            return ""

    def add_document(
        self,
        content: str,
        doc_id: str,
        metadata: dict | None = None,
    ) -> None:
        """
        Add a document to the RAG corpus.

        Args:
            content: Text content to index.
            doc_id: Unique document identifier.
            metadata: Optional metadata dict (domain, standard, etc.).
        """
        try:
            import chromadb  # lazy import

            if self._client is None:
                self._client = chromadb.PersistentClient(path=self.chroma_db_path)

            if self._collection is None:
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name
                )

            self._collection.upsert(
                ids=[doc_id],
                documents=[content],
                metadatas=[metadata or {}],
            )
        except Exception as exc:
            logger.error("Failed to add document to RAG corpus: %s", exc)
