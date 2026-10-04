"""The knowledge base: load the clinic's PDFs, and search them.

    ingest()   read every PDF, chunk it, embed the chunks and store them in Qdrant
    search()   find the chunks closest in meaning to a question

Both the website and the AI agent's search tool use search(). Ingest is run by a script,
not by the web app.
"""

import asyncio
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from qdrant_client import QdrantClient

from app.core.config import settings
from app.features.knowledge.chunking import Chunk, chunk_document
from app.features.knowledge.pdf_reader import read_pdf
from app.features.knowledge.vector_store import (  # noqa: F401  (re-exported for callers)
    KnowledgeIndexOutdated,
    KnowledgeNotIngested,
    VectorStore,
)

_MAX_QUESTION_CHARS = 1000


class EmbedderLike(Protocol):
    """What the knowledge base needs from an embedder. Tests pass in a fake one."""

    name: str

    def count_tokens(self, text: str) -> int: ...
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, question: str) -> list[float]: ...


@dataclass
class Passage:
    """One search result, with everything needed to quote it and say where it came from."""

    document: str
    heading: str
    text: str
    source: str
    pages: list[int]
    score: float

    @property
    def labelled_text(self) -> str:
        return f"{self.document} > {self.heading}\n{self.text}"


class KnowledgeBase:
    def __init__(self, embedder: EmbedderLike, store: VectorStore, max_chunk_tokens: int):
        self._embedder = embedder
        self._store = store
        self._max_chunk_tokens = max_chunk_tokens

    def ingest(self, pdf_paths: list[Path]) -> dict[str, int]:
        """Rebuild the whole index from these PDFs. Returns how many chunks each one gave.

        Everything is rebuilt each time rather than updated piece by piece. With a few
        hundred chunks this takes seconds, and it means a removed or renamed document can
        never leave old chunks behind.
        """
        if not pdf_paths:
            raise ValueError("No PDFs to ingest.")

        chunks: list[Chunk] = []
        per_file: dict[str, int] = {}
        for path in sorted(pdf_paths):
            document_chunks = chunk_document(read_pdf(path), self._embedder.count_tokens, self._max_chunk_tokens)
            per_file[path.name] = len(document_chunks)
            chunks.extend(document_chunks)

        vectors = self._embedder.embed_documents([c.labelled_text for c in chunks])
        self._store.replace_all(chunks, vectors, self._embedder.name)
        return per_file

    async def search(self, question: str, limit: int = 4, min_score: float | None = None) -> list[Passage]:
        """The chunks that best answer the question, best first.

        Returns an empty list when nothing is close enough. Callers must treat that as
        "the documents don't say" - never as a reason to guess.
        """
        question = question.strip()
        if not question:
            return []
        if len(question) > _MAX_QUESTION_CHARS:
            raise ValueError(f"Questions are limited to {_MAX_QUESTION_CHARS} characters.")

        cut_off = settings.knowledge_min_score if min_score is None else min_score
        # Embedding is slow CPU work. Running it in a thread keeps the server answering
        # other requests in the meantime.
        return await asyncio.to_thread(self._search, question, limit, cut_off)

    def _search(self, question: str, limit: int, min_score: float) -> list[Passage]:
        vector = self._embedder.embed_query(question)
        hits = self._store.search(vector, limit, min_score, self._embedder.name)
        return [
            Passage(
                document=p["document"],
                heading=p["heading"] + (f" (part {p['part']})" if p["part"] > 1 else ""),
                text=p["text"],
                source=p["source"],
                pages=p["pages"],
                score=round(score, 3),
            )
            for score, p in hits
        ]


# --- The shared instance used by the app ----------------------------------------------

_shared: KnowledgeBase | None = None
_shared_lock = threading.Lock()


def get_knowledge_base() -> KnowledgeBase:
    """Created on first use, then reused - loading the model takes several seconds.

    The lock stops two first requests arriving together from each creating one. That
    matters: Qdrant's local mode allows only one client per folder.
    """
    global _shared
    with _shared_lock:
        if _shared is None:
            from app.features.knowledge.embeddings import Embedder

            store = VectorStore(QdrantClient(path=settings.qdrant_path), settings.knowledge_collection)
            _shared = KnowledgeBase(Embedder(settings.embedding_model), store, settings.knowledge_max_chunk_tokens)
        return _shared


def close_knowledge_base() -> None:
    """Close the shared instance, if one was created. Safe to call when none was."""
    global _shared
    with _shared_lock:
        if _shared is not None:
            _shared._store.close()
            _shared = None
