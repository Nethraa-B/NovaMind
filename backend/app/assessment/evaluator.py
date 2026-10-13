from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import AssessmentLog, AssessmentQuestion


def _normalize_text(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def _parse_number(value: str) -> Optional[float]:
    if value is None:
        return None
    match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", str(value))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _extract_citation(question: AssessmentQuestion) -> List[Dict[str, str]]:
    source_reference = question.source_reference or "Unknown | N/A"
    parts = [part.strip() for part in source_reference.split("|")]
    if len(parts) == 2:
        return [{"source_name": parts[0], "location": parts[1]}]
    return [{"source_name": question.topic or "Unknown", "location": source_reference}]


def evaluate_submission(db: Session, question: AssessmentQuestion, student_answer: str) -> Dict[str, Any]:
    student_text = _normalize_text(student_answer)
    correct_answer = str(question.correct_answer or "").strip()
    correct_text = _normalize_text(correct_answer)
    question_type = (question.question_type or "mcq").lower()

    if question_type == "mcq":
        if not question.options:
            correctness = student_text == correct_text
            score = 1.0 if correctness else 0.0
            explanation = "Multiple-choice answer evaluated exactly against the stored correct answer."
        else:
            normalized_options = {_normalize_text(option): option for option in question.options}
            correctness = student_text in normalized_options and normalized_options[student_text] == correct_answer
            score = 1.0 if correctness else 0.0
            explanation = "MCQ evaluated deterministically using the stored answer key." if correctness else f"The correct answer is {correct_answer}."
    elif question_type == "numerical":
        student_number = _parse_number(student_answer)
        correct_number = _parse_number(correct_answer)
        if student_number is None or correct_number is None:
            correctness = False
            score = 0.0
            explanation = "The submitted answer could not be parsed as a numeric value."
        else:
            tolerance = max(0.05 * max(abs(correct_number), 1.0), 0.01)
            correctness = abs(student_number - correct_number) <= tolerance
            score = 1.0 if correctness else 0.0
            explanation = "Numerical answer matched the expected value within an acceptable tolerance." if correctness else f"The correct value is {correct_answer}."
    else:
        correct_tokens = set(re.findall(r"[a-zA-Z0-9]+", correct_text))
        student_tokens = set(re.findall(r"[a-zA-Z0-9]+", student_text))
        overlap = len(correct_tokens & student_tokens)
        precision = overlap / max(1, len(student_tokens))
        recall = overlap / max(1, len(correct_tokens))
        score = max(0.0, min(1.0, (precision + recall) / 2.0))
        correctness = score >= 0.6
        explanation = "Short-answer response was accepted based on meaningful keyword overlap with the source-grounded answer." if correctness else "The short-answer response was not sufficiently supported by the course material."

    source_feedback = f"Your answer is aligned with the course material for {question.topic}." if correctness else f"The answer is not supported by the course content. Review the relevant material for {question.topic}."

    return {
        "correctness": correctness,
        "score": round(score, 2),
        "explanation": explanation,
        "correct_answer": correct_answer,
        "source_grounded_feedback": source_feedback,
        "citations": _extract_citation(question),
    }


def log_assessment_result(db: Session, question: AssessmentQuestion, student_answer: str, evaluation: Dict[str, Any], misconception: Optional[str] = None) -> AssessmentLog:
    log = AssessmentLog(
        question_id=question.id,
        student_answer=student_answer,
        is_correct=1 if evaluation["correctness"] else 0,
        misconception_detected=misconception,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
