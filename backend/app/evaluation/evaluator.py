from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import AssessmentQuestion
from app.schemas import AskResponse


def reference_token_f1(generated: str, reference: str) -> float:
    generated_tokens = set(re.findall(r"[a-z0-9]+", generated.lower()))
    reference_tokens = set(re.findall(r"[a-z0-9]+", reference.lower()))
    if not generated_tokens or not reference_tokens:
        return 0.0
    overlap = len(generated_tokens & reference_tokens)
    precision = overlap / len(generated_tokens)
    recall = overlap / len(reference_tokens)
    return round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0


def run_model_evaluation(
    db: Session,
    answer_with_sources: Callable[[str, Optional[str], Optional[str]], Tuple[AskResponse, List[Dict[str, Any]]]],
    citations_match: Callable[[str, List[Dict[str, Any]]], bool],
) -> Dict[str, Any]:
    questions = db.query(AssessmentQuestion).order_by(AssessmentQuestion.id.asc()).limit(10).all()
    if not questions:
        raise ValueError("No stored assessment questions are available to evaluate. Generate questions from uploaded material first.")

    cases = []
    skipped = 0
    for question in questions:
        response, retrieved = answer_with_sources(question.question_text, question.topic, question.concept)
        if not retrieved:
            skipped += 1
            continue
        cases.append(
            {
                "question_id": question.id,
                "question": question.question_text,
                "reference_answer": question.correct_answer,
                "generated_answer": response.answer,
                "supported": response.supported,
                "citation_valid": citations_match(response.answer, retrieved),
                "reference_token_f1": reference_token_f1(response.answer, question.correct_answer),
                "citations": [citation.model_dump() for citation in response.citations],
            }
        )

    if not cases:
        raise ValueError("No assessment questions had retrievable course context; no model outputs were evaluated.")
    return {
        "status": "completed",
        "cases_evaluated": len(cases),
        "cases_skipped": skipped,
        "supported_response_rate": round(sum(case["supported"] for case in cases) / len(cases), 4),
        "citation_validity": round(sum(case["citation_valid"] for case in cases) / len(cases), 4),
        "mean_reference_token_f1": round(sum(case["reference_token_f1"] for case in cases) / len(cases), 4),
        "cases": cases,
    }
