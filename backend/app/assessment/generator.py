
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.learner.mastery import get_weak_topics
from app.models import AssessmentQuestion, ContentChunk, Topic


def _build_mcqs(
    topic: str, concept: str, text: str, chunk: ContentChunk
) -> List[Dict[str, Any]]:
    lower = text.lower()
    source = f"{chunk.source_name} | {chunk.location_ref}"
    questions: List[Dict[str, Any]] = []

    # Transaction questions: use only chunks containing actual ACID details.
    is_transaction_topic = (
        "transaction" in topic.lower()
        or "concurrency" in topic.lower()
    )

    if is_transaction_topic:
        if "atomicity:" in lower or "atomicity" in lower:
            questions.append({
                "topic": topic,
                "concept": concept,
                "difficulty": "medium",
                "question_type": "mcq",
                "question_text": (
                    "During a bank transfer, money is debited from one "
                    "account but not credited to the other. Which ACID "
                    "property requires the transaction to be all-or-nothing?"
                ),
                "options": [
                    "Atomicity", "Consistency", "Isolation", "Durability"
                ],
                "correct_answer": "Atomicity",
                "source_reference": source,
            })

        if "durability:" in lower or "durability" in lower:
            questions.append({
                "topic": topic,
                "concept": concept,
                "difficulty": "medium",
                "question_type": "mcq",
                "question_text": (
                    "Which ACID property ensures committed changes survive "
                    "system failures?"
                ),
                "options": [
                    "Atomicity", "Consistency", "Isolation", "Durability"
                ],
                "correct_answer": "Durability",
                "source_reference": source,
            })

        if "consistency:" in lower or "consistency" in lower:
            questions.append({
                "topic": topic,
                "concept": concept,
                "difficulty": "medium",
                "question_type": "mcq",
                "question_text": (
                    "Which ACID property ensures a transaction preserves "
                    "the database's valid rules and constraints?"
                ),
                "options": [
                    "Atomicity", "Consistency", "Isolation", "Durability"
                ],
                "correct_answer": "Consistency",
                "source_reference": source,
            })

        if "isolation:" in lower or "isolation" in lower:
            questions.append({
                "topic": topic,
                "concept": concept,
                "difficulty": "medium",
                "question_type": "mcq",
                "question_text": (
                    "Which ACID property helps concurrent transactions "
                    "operate without improperly interfering with each other?"
                ),
                "options": [
                    "Atomicity", "Consistency", "Isolation", "Durability"
                ],
                "correct_answer": "Isolation",
                "source_reference": source,
            })

        if "rollback" in lower or "bank-transfer" in lower or "bank transfer" in lower:
            questions.append({
                "topic": topic,
                "concept": concept,
                "difficulty": "easy",
                "question_type": "mcq",
                "question_text": (
                    "A transaction fails halfway through a bank transfer. "
                    "What should happen to preserve atomicity?"
                ),
                "options": [
                    "Keep only the debit",
                    "Keep only the credit",
                    "Roll back the incomplete transaction",
                    "Ignore the failure"
                ],
                "correct_answer": "Roll back the incomplete transaction",
                "source_reference": source,
            })

        return questions

    # Normalization questions for non-transaction topics.
    if "1nf" in lower or "first normal form" in lower:
        questions.append({
            "topic": topic,
            "concept": concept,
            "difficulty": "easy",
            "question_type": "mcq",
            "question_text": (
                "Which normal form requires each attribute to contain "
                "atomic values?"
            ),
            "options": ["1NF", "2NF", "3NF", "BCNF"],
            "correct_answer": "1NF",
            "source_reference": source,
        })

    if "2nf" in lower or "partial functional dependencies" in lower:
        questions.append({
            "topic": topic,
            "concept": concept,
            "difficulty": "medium",
            "question_type": "mcq",
            "question_text": (
                "Which normal form removes partial functional dependencies?"
            ),
            "options": ["1NF", "2NF", "3NF", "BCNF"],
            "correct_answer": "2NF",
            "source_reference": source,
        })

    if "3nf" in lower or "transitive dependencies" in lower:
        questions.append({
            "topic": topic,
            "concept": concept,
            "difficulty": "medium",
            "question_type": "mcq",
            "question_text": (
                "Which normal form aims to remove transitive dependencies?"
            ),
            "options": ["1NF", "2NF", "3NF", "BCNF"],
            "correct_answer": "3NF",
            "source_reference": source,
        })

    if "primary key" in lower:
        questions.append({
            "topic": topic,
            "concept": concept,
            "difficulty": "easy",
            "question_type": "mcq",
            "question_text": (
                "What is the main purpose of a primary key in a relational table?"
            ),
            "options": [
                "Store duplicate records",
                "Uniquely identify each row",
                "Create a view",
                "Sort every column automatically",
            ],
            "correct_answer": "Uniquely identify each row",
            "source_reference": source,
        })

    return questions


def _validate_question(question: Dict[str, Any]) -> bool:
    required = [
        "topic", "concept", "difficulty", "question_type",
        "question_text", "correct_answer", "source_reference"
    ]

    if any(not question.get(field) for field in required):
        return False

    if question["question_type"] == "mcq":
        options = question.get("options")
        if not isinstance(options, list) or len(options) < 2:
            return False
        if question["correct_answer"] not in options:
            return False

    return bool(question["source_reference"].strip())


def _chunks_for_topic(
    db: Session, topic_name: str | None
) -> List[ContentChunk]:
    query = db.query(ContentChunk)

    if topic_name:
        topic_row = db.query(Topic).filter(Topic.name == topic_name).first()
        if topic_row:
            query = query.filter(ContentChunk.topic_id == topic_row.id)

    return query.order_by(ContentChunk.id.asc()).all()


def generate_assessment_questions(
    db: Session, topic: str | None = None, limit: int = 3
) -> List[AssessmentQuestion]:
    if limit < 1:
        return []

    if topic:
        selected_topics = [topic]
    else:
        selected_topics = [
            item["topic"]
            for item in get_weak_topics(db, limit=5)
            if item.get("topic")
        ]

    if not selected_topics:
        selected_topics = [
            row[0] for row in db.query(Topic.name).all()
        ][:5]

    created: List[AssessmentQuestion] = []
    seen_texts = set()

    for topic_name in selected_topics:
        for chunk in _chunks_for_topic(db, topic_name):
            concept = (
                chunk.concept.name
                if chunk.concept
                else "General Course Content"
            )

            for candidate in _build_mcqs(
                topic_name, concept, chunk.content, chunk
            ):
                if not _validate_question(candidate):
                    continue

                question_text = candidate["question_text"]

                if question_text in seen_texts:
                    continue
                seen_texts.add(question_text)

                existing = (
                    db.query(AssessmentQuestion)
                    .filter(
                        AssessmentQuestion.question_text == question_text
                    )
                    .first()
                )

                if existing:
                    created.append(existing)
                else:
                    question = AssessmentQuestion(
                        topic=candidate["topic"],
                        concept=candidate["concept"],
                        difficulty=candidate["difficulty"],
                        question_type=candidate["question_type"],
                        question_text=question_text,
                        options=candidate.get("options"),
                        correct_answer=candidate["correct_answer"],
                        source_reference=candidate["source_reference"],
                    )
                    db.add(question)
                    db.commit()
                    db.refresh(question)
                    created.append(question)

                if len(created) >= limit:
                    return created[:limit]

    return created[:limit]
