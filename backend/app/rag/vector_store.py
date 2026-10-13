from __future__ import annotations

from hashlib import sha256
from functools import lru_cache
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import chromadb
except ImportError:  # pragma: no cover - optional dependency
    chromadb = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - optional dependency
    SentenceTransformer = None

from app.config import CHROMA_PERSIST_DIR

_FALLBACK_STORE: List[Dict[str, Any]] = []


def _simple_embedding(text: str) -> np.ndarray:
    tokens = [token.lower() for token in text.replace("-", " ").split() if token.strip()]
    vector = np.zeros(32, dtype=float)
    if not tokens:
        return vector
    counts: Dict[int, float] = {}
    for token in tokens:
        idx = int.from_bytes(sha256(token.encode("utf-8")).digest()[:4], "big") % 32
        counts[idx] = counts.get(idx, 0.0) + 1.0
    for idx, value in counts.items():
        vector[idx] = value
    norm = float(np.linalg.norm(vector))
    if norm > 0:
        vector = vector / norm
    return vector


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def _get_client() -> Any:
    if chromadb is None:
        return None
    return chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))


@lru_cache(maxsize=1)
def _get_embedder() -> Any:
    if SentenceTransformer is not None:
        return SentenceTransformer("all-MiniLM-L6-v2")
    return None


def get_collection() -> Any:
    client = _get_client()
    if client is None:
        return None
    return client.get_or_create_collection(name="novamind_chunks", metadata={"hnsw:space": "cosine"})


def store_chunks(chunks: List[Dict[str, Any]]) -> None:
    if not chunks:
        return

    collection = get_collection()
    embedder = _get_embedder()
    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    embeddings: List[List[float]] = []

    for chunk in chunks:
        content = str(chunk.get("content", "")).strip()
        if not content:
            continue

        chunk_hash = str(chunk.get("chunk_hash") or sha256(content.encode("utf-8")).hexdigest())
        material_id = chunk.get("material_id")
        source_name = chunk.get("source_name", "unknown")
        source_type = chunk.get("source_type", "unknown")
        location = chunk.get("location_ref", "N/A")
        topic = chunk.get("topic", "Uncategorized")
        concept = chunk.get("concept", "General Course Content")

        chunk_id = sha256(f"{material_id}:{chunk_hash}".encode("utf-8")).hexdigest()
        if collection is None:
            existing_ids = {item["chunk_id"] for item in _FALLBACK_STORE}
            if chunk_id in existing_ids:
                continue
            _FALLBACK_STORE.append(
                {
                    "chunk_id": chunk_id,
                    "content": content,
                    "embedding": _simple_embedding(content),
                    "material_id": str(material_id),
                    "source_name": source_name,
                    "source_type": source_type,
                    "location_ref": location,
                    "topic": topic,
                    "concept": concept,
                }
            )
            continue

        ids.append(chunk_id)
        documents.append(content)
        metadatas.append(
            {
                "material_id": str(material_id),
                "source_name": source_name,
                "source_type": source_type,
                "location_ref": location,
                "topic": topic,
                "concept": concept,
            }
        )

    if not documents or collection is None:
        return

    if embedder is not None:
        embeddings = embedder.encode(documents, show_progress_bar=False).tolist()
        collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
    else:
        collection.add(ids=ids, documents=documents, metadatas=metadatas)


def search_chunks(query: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    collection = get_collection()
    if collection is None:
        items = []
        query_vector = _simple_embedding(query)
        for item in _FALLBACK_STORE:
            if filters:
                matched = True
                for key, value in filters.items():
                    if str(item.get(key, "")) != str(value):
                        matched = False
                        break
                if not matched:
                    continue
            similarity = _cosine_similarity(query_vector, item["embedding"])
            if similarity <= 0:
                continue
            items.append((similarity, item))
        items.sort(key=lambda pair: pair[0], reverse=True)
        return [
            {
                "content": item["content"],
                "source_name": item.get("source_name", "unknown"),
                "source_type": item.get("source_type", "unknown"),
                "location_ref": item.get("location_ref", "N/A"),
                "topic": item.get("topic", "Uncategorized"),
                "concept": item.get("concept", "General Course Content"),
                "material_id": item.get("material_id"),
            }
            for _, item in items[:top_k]
        ]

    embedder = _get_embedder()
    if embedder is None:
        result = collection.query(query_texts=[query], n_results=top_k, where=filters)
    else:
        query_vector = embedder.encode([query], show_progress_bar=False)[0].tolist()
        result = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=filters,
        )

    if not result or not result.get("documents"):
        return []

    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    output = []
    for document, metadata in zip(docs, metas):
        output.append({
            "content": document,
            "source_name": metadata.get("source_name", "unknown"),
            "source_type": metadata.get("source_type", "unknown"),
            "location_ref": metadata.get("location_ref", "N/A"),
            "topic": metadata.get("topic", "Uncategorized"),
            "concept": metadata.get("concept", "General Course Content"),
            "material_id": metadata.get("material_id"),
        })
    return output
