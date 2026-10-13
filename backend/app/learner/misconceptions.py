from __future__ import annotations

from typing import Optional


def detect_misconception(topic: str, question_type: str, student_answer: str, correct_answer: str) -> Optional[str]:
    student = (student_answer or "").lower()
    correct = (correct_answer or "").lower()
    topic_name = (topic or "").lower()
    if "serializability" in correct and "isolation" in student and "serializability" not in student:
        return "Confuses conflict serializability with isolation levels."
    if "durability" in correct and "atomicity" in student:
        return "Confuses durability with atomicity in ACID properties."
    if "primary key" in correct and "foreign key" in student:
        return "Mixes up primary and foreign key semantics."
    if "index" in topic_name and "table scan" in student:
        return "Assumes indexing is unnecessary, overlooking how indexes improve retrieval."
    if question_type == "mcq" and student and correct and student in {"isolation", "serializability"}:
        return "The student is selecting a concept that is closely related but not the correct one for the question."
    return None
