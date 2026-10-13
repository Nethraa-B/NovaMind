from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.rag.vector_store import search_chunks


def retrieve_context(question: str, material_id: Optional[int] = None, topic: Optional[str] = None, concept: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
    filters: Dict[str, Any] = {}
    if material_id is not None:
        filters["material_id"] = str(material_id)
    if topic:
        filters["topic"] = topic
    if concept:
        filters["concept"] = concept

    chunks = search_chunks(query=question, top_k=top_k, filters=filters or None)
    if not chunks:
        return []

    # Keep the top-ranked source document as the grounding scope. This prevents
    # semantically adjacent passages from unrelated uploaded courses from
    # diluting the answer context or its citation checks.
    primary_material_id = chunks[0].get("material_id")
    if primary_material_id is not None:
        focused_chunks = [
            chunk
            for chunk in chunks
            if str(chunk.get("material_id")) == str(primary_material_id)
        ]
        if focused_chunks:
            chunks = focused_chunks
    else:
        primary_source = chunks[0].get("source_name")
        focused_chunks = [
            chunk for chunk in chunks if chunk.get("source_name") == primary_source
        ]
        if focused_chunks:
            chunks = focused_chunks

    normalized: List[Dict[str, Any]] = []
    for chunk in chunks:
        normalized.append(
            {
                "content": chunk.get("content", ""),
                "source_name": chunk.get("source_name", "unknown"),
                "source_type": chunk.get("source_type", "unknown"),
                "location_ref": chunk.get("location_ref", "N/A"),
                "topic": chunk.get("topic", "Uncategorized"),
                "concept": chunk.get("concept", "General Course Content"),
                "material_id": chunk.get("material_id"),
            }
        )
    return normalized
