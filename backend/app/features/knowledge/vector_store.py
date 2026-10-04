"""Stores chunk vectors in Qdrant and searches them.

This is the only file that knows about Qdrant. Qdrant keeps each chunk's text and details
alongside its vector, so there is no separate table for chunks.

Local mode (QdrantClient(path=...)) keeps everything in a folder, with no server to run.
Moving to a Qdrant server later only changes how the client is created.
"""

import threading
import uuid
from dataclasses import asdict

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.features.knowledge.chunking import Chunk

_UPLOAD_BATCH = 64


class KnowledgeNotIngested(Exception):
    """Search was asked for before the documents were loaded."""


class KnowledgeIndexOutdated(Exception):
    """The stored vectors were made by a different embedding model.

    Vectors from two different models can't be compared - the scores would be
    meaningless - so search refuses to run until the documents are ingested again.
    """


class VectorStore:
    def __init__(self, client: QdrantClient, collection: str):
        self._client = client
        self._collection = collection
        self._lock = threading.Lock()  # one operation at a time on the shared client

    def replace_all(self, chunks: list[Chunk], vectors: list[list[float]], model_name: str) -> None:
        """Throw away what is stored and store these chunks instead."""
        if len(chunks) != len(vectors) or not chunks:
            raise ValueError("Need the same, non-zero number of chunks and vectors.")

        points = [
            PointStruct(
                # The same chunk always gets the same id, so re-running ingest is repeatable.
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{chunk.source}#{index}")),
                vector=vector,
                payload={**asdict(chunk), "label": chunk.label, "embedding_model": model_name},
            )
            for index, (chunk, vector) in enumerate(zip(chunks, vectors))
        ]
        with self._lock:
            if self._client.collection_exists(self._collection):
                self._client.delete_collection(self._collection)
            self._client.create_collection(
                self._collection,
                vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE),
            )
            for start in range(0, len(points), _UPLOAD_BATCH):
                self._client.upsert(self._collection, points=points[start : start + _UPLOAD_BATCH])

    def search(self, vector: list[float], limit: int, min_score: float, model_name: str) -> list[tuple[float, dict]]:
        """The closest chunks, best first, leaving out any that score below min_score."""
        with self._lock:
            if not self._client.collection_exists(self._collection):
                raise KnowledgeNotIngested("The clinic documents haven't been loaded. Run the ingest script.")
            # No score cut-off here. The model check below has to see results even when
            # they would all be cut - otherwise vectors from the wrong model would just
            # look like "nothing relevant found", with no error.
            hits = self._client.query_points(
                self._collection, query=vector, limit=limit, with_payload=True
            ).points

        for hit in hits:
            if hit.payload.get("embedding_model") != model_name:
                raise KnowledgeIndexOutdated(
                    f"Stored vectors were made with {hit.payload.get('embedding_model')!r} but the "
                    f"app now uses {model_name!r}. Run the ingest script again."
                )
        return [(hit.score, hit.payload) for hit in hits if hit.score >= min_score]

    def close(self) -> None:
        """Release the Qdrant folder, so another program (like the ingest script) can use it."""
        with self._lock:
            self._client.close()

    def count(self) -> int:
        with self._lock:
            if not self._client.collection_exists(self._collection):
                return 0
            return self._client.count(self._collection).count
