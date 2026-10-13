from __future__ import annotations

import re
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.assessment.evaluator import evaluate_submission, log_assessment_result
from app.assessment.generator import generate_assessment_questions
from app.config import BASE_DIR, CORS_ORIGINS
from app.database import get_db, init_db
from app.ingestion.processor import process_upload
from app.learner.mastery import get_mastery, get_weak_topics, update_mastery
from app.learner.misconceptions import detect_misconception
from app.learner.recommendations import generate_recommendations
from app.llm import LLMError, generate_text
from app.models import AssessmentQuestion, ContentChunk, Material
from app.rag.prompts import build_grounded_prompt
from app.rag.retriever import retrieve_context
from app.rag.vector_store import store_chunks
from app.schemas import (
    AskRequest,
    AskResponse,
    AssessmentGenerateRequest,
    AssessmentGenerateResponse,
    AssessmentSubmission,
    AssessmentSubmissionResult,
    Citation,
    EvaluationRunResult,
    MaterialOut,
    QuestionOut,
)

logger = logging.getLogger(__name__)
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="NovaMind API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.evaluation_results: Optional[Dict[str, Any]] = None

_CITATION_REFERENCE = re.compile(
    r"\[([^\[\]|]+?)\s*\|\s*([^\[\]|]+?)\]"
    r"|【([^【】|]+?)\s*\|\s*([^【】|]+?)】"
)
_GROUNDING_STOP_WORDS = {
    "a", "about", "after", "also", "an", "and", "are", "as", "at", "be",
    "because", "before", "between", "by", "can", "could", "does", "for",
    "from", "has", "have", "how", "in", "into", "is", "it", "its", "may",
    "more", "not", "of", "on", "one", "or", "such", "than", "that", "the",
    "their", "then", "there", "these", "this", "those", "through", "to", "use",
    "used", "using", "was", "were", "what", "when", "which", "while", "with",
    "taken", "directly", "course", "material", "pdf", "source", "file",
    "document", "documents", "uploaded", "lists", "list", "listed",
    "mentioned", "mentions", "above", "points", "drawn", "based",
}
_SOURCE_HINT_STOP_WORDS = _GROUNDING_STOP_WORDS | {
    "file", "files", "document", "documents", "source", "sources", "uploaded",
    "upload", "mentioned", "mention", "according", "pdf", "ppt", "pptx", "mp4",
}


def _normalize_citation_text(value: str) -> str:
    """Normalize source labels without changing their meaningful content."""
    value = value.replace("\\", "/").strip().casefold()
    value = re.sub(r"\s+", " ", value)
    value = value.replace("_", " ")
    return value.strip()


def _normalize_citation_source(value: str) -> str:
    value = re.sub(r"^source\s*:\s*", "", value.strip(), flags=re.IGNORECASE)
    return _normalize_citation_text(value)


def _material_id_from_question(question: str, db: Session) -> Optional[int]:
    question_terms = {
        term
        for term in re.findall(r"[a-z0-9]+", question.casefold())
        if len(term) > 2 and term not in _SOURCE_HINT_STOP_WORDS
    }
    if not question_terms:
        return None

    ranked_materials = []
    for material in db.query(Material).all():
        filename_terms = {
            term
            for term in re.findall(r"[a-z0-9]+", Path(material.filename).stem.casefold())
            if len(term) > 2 and term not in _SOURCE_HINT_STOP_WORDS
        }
        overlap = question_terms & filename_terms
        if overlap:
            ranked_materials.append((len(overlap), material.id))

    if not ranked_materials:
        return None

    highest_score = max(score for score, _ in ranked_materials)
    winners = [material_id for score, material_id in ranked_materials if score == highest_score]
    return winners[0] if len(winners) == 1 else None


def _citations_match_retrieved_chunks(
    answer: str, chunks: List[Dict[str, Any]]
) -> bool:
    """
    Verify a citation against retrieved chunks.

    Accepts [source | Page 3] citations and minor filename/spacing differences.
    The source and location must still match a retrieved chunk.
    """
    if not chunks or not answer.strip():
        return False

    allowed_pairs = []
    for chunk in chunks:
        source = str(chunk.get("source_name", "")).strip()
        location = str(chunk.get("location_ref", "")).strip()
        if source and location and location.casefold() not in {"n/a", "unknown"}:
            allowed_pairs.append(
                (_normalize_citation_text(source), _normalize_citation_text(location))
            )

    if not allowed_pairs:
        return False

    citation_refs = []
    for match in _CITATION_REFERENCE.finditer(answer):
        cited_source = match.group(1) or match.group(3)
        cited_location = match.group(2) or match.group(4)
        citation_refs.append(
            (
                _normalize_citation_source(cited_source),
                _normalize_citation_text(cited_location),
            )
        )

    if not citation_refs:
        return False

    for cited_source, cited_location in citation_refs:
        if not any(
            cited_source == allowed_source
            and cited_location == allowed_location
            for allowed_source, allowed_location in allowed_pairs
        ):
            return False

    return True


def _citations_used_in_answer(
    answer: str, chunks: List[Dict[str, Any]]
) -> List[Citation]:
    used: List[Citation] = []
    seen = set()
    for match in _CITATION_REFERENCE.finditer(answer):
        cited_source = match.group(1) or match.group(3)
        cited_location = match.group(2) or match.group(4)
        normalized_source = _normalize_citation_source(cited_source)
        normalized_location = _normalize_citation_text(cited_location)
        for chunk in chunks:
            source_name = str(chunk.get("source_name", ""))
            location = str(chunk.get("location_ref", ""))
            key = (normalized_source, normalized_location)
            if (
                key not in seen
                and normalized_source == _normalize_citation_text(source_name)
                and normalized_location == _normalize_citation_text(location)
            ):
                used.append(Citation(source_name=source_name, location=location))
                seen.add(key)
                break
    return used


def _grounding_terms(value: str) -> set[str]:
    terms = set(re.findall(r"[a-z0-9]+", value.casefold()))
    return {
        term
        for term in terms
        if len(term) > 2 and term not in _GROUNDING_STOP_WORDS
    }


def _claims_match_cited_context(
    answer: str, chunks: List[Dict[str, Any]]
) -> bool:
    cited_chunks = []
    for match in _CITATION_REFERENCE.finditer(answer):
        cited_source = match.group(1) or match.group(3)
        cited_location = match.group(2) or match.group(4)
        normalized_source = _normalize_citation_source(cited_source)
        normalized_location = _normalize_citation_text(cited_location)
        cited_chunks.extend(
            chunk
            for chunk in chunks
            if _normalize_citation_text(str(chunk.get("source_name", "")))
            == normalized_source
            and _normalize_citation_text(str(chunk.get("location_ref", "")))
            == normalized_location
        )

    evidence_terms = set().union(
        *(
            _grounding_terms(str(chunk.get("content", "")))
            for chunk in cited_chunks
        )
    ) if cited_chunks else set()
    if not evidence_terms:
        return False

    answer_without_citations = _CITATION_REFERENCE.sub("", answer)
    clauses = re.split(
        r"(?<=[.!?])\s+|[;\n]+|\s+(?:and|but|however|whereas|while|using|via|such as)\s+",
        answer_without_citations,
        flags=re.IGNORECASE,
    )
    checked_clauses = 0

    for clause in clauses:
        claim_terms = _grounding_terms(clause)
        if not claim_terms:
            continue

        overlap = claim_terms & evidence_terms
        minimum_overlap = 1 if len(claim_terms) == 1 else 2
        minimum_coverage = 0.5 if len(claim_terms) <= 3 else 0.35
        if len(overlap) < minimum_overlap or len(overlap) / len(claim_terms) < minimum_coverage:
            return False
        checked_clauses += 1

    return checked_clauses > 0


def _is_explicitly_unsupported(answer: str) -> bool:
    """Recognize a model response that says the source lacks the answer."""
    text = answer.casefold()
    unsupported_markers = (
        "insufficient evidence",
        "does not provide enough",
        "doesn't provide enough",
        "not enough information",
        "cannot answer from the provided material",
        "can't answer from the provided material",
        "course context does not support",
        "not supported by the course material",
        "not explicitly covered",
        "not explicitly mentioned",
        "not explicitly listed",
        "does not explicitly list",
        "doesn't explicitly list",
        "does not specify",
        "doesn't specify",
        "not covered in the provided material",
        "not mentioned in the provided material",
        "the provided material does not",
        "the course material does not",
    )
    return any(marker in text for marker in unsupported_markers)


def _answer_from_context(
    question: str, retrieved: List[Dict[str, Any]]
) -> AskResponse:
    citations = [
        Citation(
            source_name=item.get("source_name", "unknown"),
            location=item.get("location_ref", "N/A"),
        )
        for item in retrieved
    ]

    if not retrieved:
        return AskResponse(
            answer=(
                "The uploaded course material does not provide enough direct "
                "evidence to answer this question confidently."
            ),
            supported=False,
            citations=[],
        )

    prompt = build_grounded_prompt(question, retrieved)
    for attempt in range(2):
        answer = generate_text(prompt).strip()

        if not answer:
            return AskResponse(
                answer=(
                    "The model did not generate an answer. Please try a more "
                    "specific question about the uploaded material."
                ),
                supported=False,
                citations=citations,
            )

        # Preserve a clear model abstention rather than trying to reword it.
        if _is_explicitly_unsupported(answer):
            return AskResponse(
                answer=answer,
                supported=False,
                citations=citations,
            )

        if (
            _citations_match_retrieved_chunks(answer, retrieved)
            and _claims_match_cited_context(answer, retrieved)
        ):
            return AskResponse(
                answer=answer,
                supported=True,
                citations=_citations_used_in_answer(answer, retrieved),
            )

        if attempt == 0:
            prompt += (
                "\n\nYour previous response failed source verification. "
                "Rewrite it as concise plain-text bullets, not a table. "
                "Use only definitions, examples, and relationships stated "
                "in the retrieved text. Do not add database mechanisms, "
                "constraints, schedules, or implementation details that are "
                "not present there. Cite each factual bullet with the exact "
                "source and location using [source_name | location_ref]. "
                "If a requested detail is not in the source, omit it or say "
                "that the source does not provide it."
            )

    return AskResponse(
        answer=(
            "I retrieved course material, but could not verify that the "
            "generated claims are supported by a cited source. Please try "
            "a more specific question."
        ),
        supported=False,
        citations=citations,
    )


def _answer_with_sources(
    question: str,
    topic: Optional[str] = None,
    concept: Optional[str] = None,
):
    retrieved = retrieve_context(question, topic=topic, concept=concept)
    return _answer_from_context(question, retrieved), retrieved


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "novamind"}


@app.post(
    "/api/upload",
    response_model=MaterialOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_material(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> MaterialOut:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A file name is required.",
        )

    extension = Path(file.filename).suffix.lower()
    supported = {".pdf", ".pptx", ".mp4"}

    if extension not in supported:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type: {file.filename}. "
                "Supported types: PDF, PPTX, MP4."
            ),
        )

    safe_name = Path(file.filename).name
    target_path = UPLOAD_DIR / safe_name
    material: Optional[Material] = None

    if target_path.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate upload detected for {safe_name}.",
        )

    try:
        with target_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        material = process_upload(safe_name, str(target_path))
        chunks = (
            db.query(ContentChunk)
            .filter(ContentChunk.material_id == material.id)
            .all()
        )

        vector_chunks = [
            {
                "content": chunk.content,
                "material_id": chunk.material_id,
                "source_name": chunk.source_name,
                "source_type": chunk.source_type,
                "location_ref": chunk.location_ref,
                "topic": (
                    chunk.topic.name if chunk.topic else "Uncategorized"
                ),
                "concept": (
                    chunk.concept.name
                    if chunk.concept
                    else "General Course Content"
                ),
                "chunk_hash": chunk.chunk_hash,
            }
            for chunk in chunks
        ]

        store_chunks(vector_chunks)

        return MaterialOut(
            id=material.id,
            filename=material.filename,
            file_type=material.file_type,
            upload_date=material.upload_date,
        )
    except ValueError as exc:
        if material is None:
            target_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Upload processing failed for %s", safe_name)
        if material is None:
            target_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Upload processing failed before the material was saved."
                if material is None
                else "The material was saved, but retrieval indexing failed. Refresh the library before retrying."
            ),
        ) from exc


@app.get("/api/materials", response_model=list[MaterialOut])
def list_materials(db: Session = Depends(get_db)) -> list[MaterialOut]:
    materials = db.query(Material).order_by(Material.id.desc()).all()

    return [
        MaterialOut(
            id=material.id,
            filename=material.filename,
            file_type=material.file_type,
            upload_date=material.upload_date,
        )
        for material in materials
    ]


@app.get("/api/materials/{material_id}", response_model=MaterialOut)
def get_material(
    material_id: int, db: Session = Depends(get_db)
) -> MaterialOut:
    material = (
        db.query(Material)
        .filter(Material.id == material_id)
        .first()
    )

    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found.",
        )

    return MaterialOut(
        id=material.id,
        filename=material.filename,
        file_type=material.file_type,
        upload_date=material.upload_date,
    )


@app.post("/api/ask", response_model=AskResponse)
def ask_question(
    payload: AskRequest,
    db: Session = Depends(get_db),
) -> AskResponse:
    try:
        material_id = _material_id_from_question(payload.question, db)
        retrieved = retrieve_context(
            payload.question,
            material_id=material_id,
            topic=payload.topic,
            concept=payload.concept,
        )
    except Exception as exc:
        logger.exception("Course retrieval failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Course retrieval is temporarily unavailable.",
        ) from exc

    try:
        return _answer_from_context(payload.question, retrieved)
    except LLMError:
        citations = [
            Citation(
                source_name=item.get("source_name", "unknown"),
                location=item.get("location_ref", "N/A"),
            )
            for item in retrieved
        ]

        return AskResponse(
            answer=(
                "The language model is unavailable. Retrieved course "
                "citations are listed below."
            ),
            supported=False,
            citations=citations,
        )


@app.post(
    "/api/assessment/generate",
    response_model=AssessmentGenerateResponse,
)
def generate_assessment(
    payload: AssessmentGenerateRequest,
    db: Session = Depends(get_db),
) -> AssessmentGenerateResponse:
    questions = generate_assessment_questions(
        db, topic=payload.topic, limit=payload.limit
    )

    response_items = [
        QuestionOut(
            id=question.id,
            topic=question.topic,
            concept=question.concept,
            difficulty=question.difficulty,
            question_type=question.question_type,
            question_text=question.question_text,
            options=question.options,
            source_reference=question.source_reference,
        )
        for question in questions
    ]

    return AssessmentGenerateResponse(questions=response_items)


@app.post(
    "/api/assessment/submit",
    response_model=AssessmentSubmissionResult,
)
def submit_assessment(
    payload: AssessmentSubmission,
    db: Session = Depends(get_db),
) -> AssessmentSubmissionResult:
    question = (
        db.query(AssessmentQuestion)
        .filter(AssessmentQuestion.id == payload.question_id)
        .first()
    )

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment question not found.",
        )

    evaluation = evaluate_submission(
        db, question, payload.student_answer
    )
    misconception = detect_misconception(
        question.topic,
        question.question_type,
        payload.student_answer,
        question.correct_answer,
    )

    log_assessment_result(
        db, question, payload.student_answer, evaluation, misconception
    )
    update_mastery(
        db,
        question.topic,
        evaluation["score"],
        question.difficulty,
        repeated_errors=0,
    )

    return AssessmentSubmissionResult(
        question_id=question.id,
        correctness=evaluation["correctness"],
        score=evaluation["score"],
        explanation=evaluation["explanation"],
        correct_answer=evaluation["correct_answer"],
        source_grounded_feedback=evaluation["source_grounded_feedback"],
        citations=evaluation["citations"],
        misconception_detected=misconception,
    )


@app.get("/api/learner/mastery")
def learner_mastery(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return {"mastery": get_mastery(db)}


@app.get("/api/learner/weak-topics")
def learner_weak_topics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return {"weak_topics": get_weak_topics(db, limit=5)}


@app.get("/api/learner/recommendations")
def learner_recommendations(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return {"recommendations": generate_recommendations(db)}


@app.post("/api/evaluation/run")
def run_evaluation(
    db: Session = Depends(get_db),
) -> EvaluationRunResult:
    try:
        from app.evaluation.evaluator import run_model_evaluation

        result = run_model_evaluation(
            db,
            _answer_with_sources,
            _citations_match_retrieved_chunks,
        )
        app.state.evaluation_results = result
        return EvaluationRunResult(**result)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@app.get("/api/evaluation/results")
def get_evaluation_results() -> Dict[str, Any]:
    if app.state.evaluation_results is None:
        return {
            "status": "not_run",
            "summary": "No evaluation has been run yet.",
        }

    return app.state.evaluation_results
