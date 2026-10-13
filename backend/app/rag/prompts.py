from __future__ import annotations

from typing import Any, Dict, List


def build_grounded_prompt(question: str, context_chunks: List[Dict[str, Any]]) -> str:
    if not context_chunks:
        return (
            "You are a course-grounded tutor. The uploaded material does not provide enough direct evidence for this question. "
            "Say that the evidence is insufficient and explain that the uploaded course content does not support a confident answer. "
            "Do not fabricate course citations."
        )

    context_block = "\n\n".join(
        f"Source: {chunk.get('source_name', 'Unknown')} | Location: {chunk.get('location_ref', 'N/A')} | Topic: {chunk.get('topic', 'Uncategorized')} | Concept: {chunk.get('concept', 'General Course Content')}\n{chunk.get('content', '')}"
        for chunk in context_chunks
    )

    return f"""
You are a strict tutor for a DBMS course.

Rules:
1. Use the retrieved course context as the primary evidence.
2. Never fabricate citations.
3. If citing a source, use only an exact source name and location from the context in the format [source_name | location_ref].
4. If the evidence is insufficient, explicitly say so.
5. Do not present outside knowledge as course-grounded knowledge.
6. If you intentionally provide outside knowledge, label it clearly as outside-course context.

Question:
{question}

Course context:
{context_block}

Answer directly using the course context. If the context does not support the answer, say so clearly and do not guess.
"""
