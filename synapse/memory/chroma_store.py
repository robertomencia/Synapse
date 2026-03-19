"""Semantic memory backed by ChromaDB."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from synapse.memory.models import MemoryEntry, Observation


class ChromaStore:
    COLLECTION = "synapse_memory"

    def __init__(self, path: Path) -> None:
        self._path = path
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None

    def connect(self) -> None:
        self._client = chromadb.PersistentClient(
            path=str(self._path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    def _col(self) -> chromadb.Collection:
        assert self._collection, "ChromaStore not connected — call connect() first"
        return self._collection

    def upsert(self, obs: Observation) -> None:
        meta: dict[str, Any] = {
            "source": obs.source,
            "event_type": obs.event_type,
            "timestamp": obs.timestamp.isoformat(),
            **{k: str(v) for k, v in obs.metadata.items()},
        }
        self._col().upsert(
            ids=[obs.id],
            documents=[obs.text],
            metadatas=[meta],
        )

    def query(self, text: str, n: int = 5) -> list[MemoryEntry]:
        from datetime import datetime

        results = self._col().query(
            query_texts=[text],
            n_results=min(n, self._col().count() or 1),
            include=["documents", "metadatas", "distances"],
        )

        entries: list[MemoryEntry] = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, distances):
            entries.append(
                MemoryEntry(
                    id=str(meta.get("id", "")),
                    text=doc,
                    source=str(meta.get("source", "")),
                    entry_type="observation",
                    timestamp=datetime.fromisoformat(
                        str(meta.get("timestamp", datetime.utcnow().isoformat()))
                    ),
                    metadata={k: v for k, v in meta.items() if k not in ("source", "timestamp")},
                    relevance_score=1.0 - float(dist),
                )
            )
        return entries

    def count(self) -> int:
        return self._col().count()
