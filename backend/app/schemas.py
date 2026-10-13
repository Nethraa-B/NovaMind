
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class Citation(BaseModel):
    source_name: str
    location: str


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Student question to answer using course material.")
    topic: Optional[str] = None
    concept: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    supported: bool
    citations: List[Citation] = Field(default_factory=list)


class MaterialOut(BaseModel):
    id: int
    filename: str
    file_type: str
    upload_date: datetime


class QuestionOut(BaseModel):
    id: Optional[int] = None
    topic: str
    concept: str
    difficulty: str
    question_type: str
    question_text: str
    options: Optional[List[str]] = None
    source_reference: str


class AssessmentGenerateRequest(BaseModel):
    topic: Optional[str] = None
    limit: int = Field(default=3, ge=1, le=10)


class AssessmentGenerateResponse(BaseModel):
    questions: List[QuestionOut]


class AssessmentSubmission(BaseModel):
    question_id: int
    student_answer: str


class AssessmentSubmissionResult(BaseModel):
    question_id: int
    correctness: bool
    score: float
    explanation: str
    correct_answer: Optional[str] = None
    source_grounded_feedback: str
    citations: List[Citation] = Field(default_factory=list)
    misconception_detected: Optional[str] = None


class MasteryEntry(BaseModel):
    topic: str
    mastery_score: float
    last_updated: datetime


class RecommendationItem(BaseModel):
    title: str
    recommendation_type: str
    topic: str
    detail: str
    source_name: Optional[str] = None
    location: Optional[str] = None


class EvaluationCaseResult(BaseModel):
    question_id: int
    question: str
    reference_answer: str
    generated_answer: str
    supported: bool
    citation_valid: bool
    reference_token_f1: float
    citations: List[Citation] = Field(default_factory=list)


class EvaluationRunResult(BaseModel):
    status: str
    cases_evaluated: int
    cases_skipped: int
    supported_response_rate: float
    citation_validity: float
    mean_reference_token_f1: float
    cases: List[EvaluationCaseResult] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: str
