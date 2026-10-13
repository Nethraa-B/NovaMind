from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pptx import Presentation
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.evaluation.evaluator import reference_token_f1, run_model_evaluation
from app.assessment.generator import generate_assessment_questions
from app.ingestion.ppt_processor import extract_ppt_chunks
from app.ingestion.processor import (
    assign_explicit_prerequisites,
    classify_topic_and_concept,
    detect_file_type,
)
from app.ingestion.video_processor import _format_timestamp, extract_video_chunks, whisper
from app.learner.mastery import get_mastery, get_weak_topics
from app.learner.misconceptions import detect_misconception
from app.learner.recommendations import generate_recommendations
from app import main
from app.llm import LLMError
from app.main import (
    _citations_match_retrieved_chunks,
    _citations_used_in_answer,
    submit_assessment,
)
from app.models import (
    AssessmentLog,
    AssessmentQuestion,
    Concept,
    ContentChunk,
    Material,
    Topic,
)
from app.rag.vector_store import _simple_embedding
from app.rag.retriever import retrieve_context
from app.schemas import AskRequest, AskResponse, AssessmentSubmission, Citation


class TrackDTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_citations_must_match_retrieved_source_and_location(self) -> None:
        chunks = [{"source_name": "DBMS course.pdf", "location_ref": "Page 4"}]
        self.assertTrue(
            _citations_match_retrieved_chunks(
                "Durability is defined here. [DBMS course.pdf | Page 4]", chunks
            )
        )
        self.assertFalse(
            _citations_match_retrieved_chunks(
                "See OtherBook.pdf, Page 99.", chunks
            )
        )
        self.assertFalse(_citations_match_retrieved_chunks("No citation included.", chunks))
        self.assertFalse(
            _citations_match_retrieved_chunks(
                "[DBMS course.pdf | Page 4] [OtherBook.pdf | Page 99]", chunks
            )
        )
        self.assertTrue(
            _citations_match_retrieved_chunks(
                "[source: DBMS course.pdf | Page 4]", chunks
            )
        )
        multiple_pages = [
            {"source_name": "DBMS course.pdf", "location_ref": "Page 1"},
            {"source_name": "DBMS course.pdf", "location_ref": "Page 2"},
        ]
        self.assertEqual(
            [citation.location for citation in _citations_used_in_answer(
                "Fact [DBMS course.pdf | Page 2]", multiple_pages
            )],
            ["Page 2"],
        )

    def test_acid_queries_keep_only_top_ranked_source_material(self) -> None:
        candidates = [
            {"content": "ACID definitions and bank transfer.", "material_id": "1", "source_name": "DBMS.pdf", "location_ref": "Page 2"},
            {"content": "Normalization overview.", "material_id": "1", "source_name": "DBMS.pdf", "location_ref": "Page 1"},
            {"content": "Encapsulation and abstraction.", "material_id": "2", "source_name": "OOP.pdf", "location_ref": "Page 2"},
            {"content": "Social Science agriculture.", "material_id": "3", "source_name": "Social Science.pdf", "location_ref": "Page 162"},
        ]
        with patch("app.rag.retriever.search_chunks", return_value=candidates):
            chunks = retrieve_context("Explain ACID properties using a bank transfer example.")

        self.assertEqual(
            [(chunk["material_id"], chunk["location_ref"]) for chunk in chunks],
            [("1", "Page 2"), ("1", "Page 1")],
        )

    def test_bank_transfer_answer_is_grounded_and_rejects_extra_mechanisms(self) -> None:
        chunks = [
            {
                "content": (
                    "Atomicity ensures all transaction operations complete or "
                    "are rolled back. The bank transfer either has both "
                    "steps succeed or neither happens. Consistency ensures total funds remain "
                    "constant. Isolation prevents a concurrent balance check "
                    "from seeing Account A debited before Account B is credited. "
                    "Durability ensures new balances persist after a server "
                    "loses power."
                ),
                "source_name": "DBMS Fundamentals_ Normalization and ACID Properties.pdf",
                "location_ref": "Page 2",
            }
        ]
        answer = (
            "Atomicity ensures both transfer steps succeed or neither does. "
            "Consistency keeps total funds constant. Isolation prevents a "
            "balance check from seeing A debited before B is credited. "
            "Durability preserves the new balances after power loss. "
            "[DBMS Fundamentals_ Normalization and ACID Properties.pdf | Page 2]"
        )
        with patch.object(main, "generate_text", return_value=answer):
            result = main._answer_from_context(
                "Explain ACID properties using a bank transfer example.", chunks
            )
        self.assertTrue(result.supported)

        unsupported_extension = answer.replace(
            "Durability preserves the new balances after power loss.",
            "Durability preserves the new balances using quantum magnetic storage after power loss.",
        )
        with patch.object(main, "generate_text", return_value=unsupported_extension):
            result = main._answer_from_context(
                "Explain ACID properties using a bank transfer example.", chunks
            )
        self.assertFalse(result.supported)

    def test_explicit_source_name_resolves_material_id(self) -> None:
        dbms = Material(
            filename="DBMS Fundamentals_ Normalization and ACID Properties.pdf",
            file_type="pdf",
        )
        social = Material(
            filename="Class_10_Social_Science_English_2025_Edition.pdf",
            file_type="pdf",
        )
        self.session.add_all([dbms, social])
        self.session.flush()

        self.assertEqual(
            main._material_id_from_question(
                "What are the ACID properties mentioned in the uploaded DBMS PDF?",
                self.session,
            ),
            dbms.id,
        )
        self.assertEqual(
            main._material_id_from_question(
                "Explain ACID properties using a bank transfer example.",
                self.session,
            ),
            dbms.id,
        )
        self.assertIsNone(
            main._material_id_from_question("Explain a bank transfer", self.session)
        )

    def test_answer_requires_supported_claims_and_an_existing_citation(self) -> None:
        chunks = [
            {
                "content": "Durability ensures committed database changes survive system failures.",
                "source_name": "dbms.pdf",
                "location_ref": "Page 4",
            }
        ]
        fullwidth_citation = chr(0x3010) + "dbms.pdf | Page 4" + chr(0x3011)
        supported_answers = [
            "Durability ensures committed database changes survive system failures. [dbms.pdf | Page 4]",
            "Durability ensures committed database changes survive system failures. "
            + fullwidth_citation,
        ]

        for answer in supported_answers:
            with self.subTest(answer=answer), patch.object(
                main, "generate_text", return_value=answer
            ):
                result = main._answer_from_context("What does durability guarantee?", chunks)
                self.assertTrue(result.supported)

        unsupported_answers = [
            "B-tree indexes in quantum devices encrypt every record. [dbms.pdf | Page 4]",
            "Durability ensures committed database changes survive system failures.",
            "Durability ensures committed database changes survive system failures. "
            "B-tree indexes encrypt every record. [dbms.pdf | Page 4]",
            "Durability ensures committed database changes survive system failures, "
            "and B-tree indexes encrypt every record. [dbms.pdf | Page 4]",
        ]

        for answer in unsupported_answers:
            with self.subTest(answer=answer), patch.object(
                main, "generate_text", return_value=answer
            ):
                result = main._answer_from_context("What does durability guarantee?", chunks)
                self.assertFalse(result.supported)
                self.assertNotIn("[dbms.pdf | Page 4]", result.answer)

        concise_properties = (
            "The PDF lists the four ACID properties of a database transaction: "
            "Atomicity - all operations in the transaction succeed or the whole "
            "transaction is rolled back. Consistency - the transaction moves "
            "the database from one valid state to another, preserving all "
            "integrity rules. Isolation - concurrent transactions run "
            "independently without seeing each other's intermediate results. "
            "Durability - once a transaction commits, its changes are permanently "
            "stored and survive system failures. These are taken directly from "
            "the course material [dbms.pdf | Page 2]."
        )
        acid_chunks = [
            {
                "content": (
                    "Atomicity ensures all transaction operations complete or "
                    "are rolled back. Consistency moves the database from one "
                    "valid state to another and obeys schema constraints. "
                    "Isolation ensures concurrent transactions execute "
                    "independently without interfering with intermediate states. "
                    "Durability ensures committed modifications are permanently "
                    "saved and survive system failures."
                ),
                "source_name": "dbms.pdf",
                "location_ref": "Page 2",
            }
        ]
        with patch.object(main, "generate_text", return_value=concise_properties):
            result = main._answer_from_context(
                "What are the ACID properties mentioned in the uploaded DBMS PDF?",
                acid_chunks,
            )
        self.assertTrue(result.supported)

    def test_failed_claim_check_gets_one_strict_retry(self) -> None:
        chunks = [
            {
                "content": "Durability preserves committed changes after a system failure.",
                "source_name": "dbms.pdf",
                "location_ref": "Page 2",
            }
        ]
        invalid = "B-tree indexes encrypt every record. [dbms.pdf | Page 2]"
        valid = "Durability preserves committed changes after a system failure. [dbms.pdf | Page 2]"
        with patch.object(main, "generate_text", side_effect=[invalid, valid]) as generate:
            result = main._answer_from_context("What does durability guarantee?", chunks)
        self.assertTrue(result.supported)
        self.assertEqual(generate.call_count, 2)
        self.assertIn("failed source verification", generate.call_args_list[1].args[0])

    def test_retry_does_not_force_unsupported_answer_to_supported(self) -> None:
        chunks = [
            {
                "content": "Durability preserves committed changes after a system failure.",
                "source_name": "dbms.pdf",
                "location_ref": "Page 2",
            }
        ]
        invalid = "B-tree indexes encrypt every record. [dbms.pdf | Page 2]"
        with patch.object(main, "generate_text", return_value=invalid) as generate:
            result = main._answer_from_context("What does durability guarantee?", chunks)
        self.assertFalse(result.supported)
        self.assertEqual(generate.call_count, 2)

    def test_explicitly_unsupported_model_answer_stays_unsupported(self) -> None:
        chunks = [
            {
                "content": "Durability ensures committed database changes survive system failures.",
                "source_name": "dbms.pdf",
                "location_ref": "Page 4",
            }
        ]
        answer = "The provided material does not specify the recovery interval."
        with patch.object(main, "generate_text", return_value=answer):
            result = main._answer_from_context("What is the recovery interval?", chunks)
        self.assertFalse(result.supported)
        self.assertEqual(result.answer, answer)

    def test_failed_pre_persistence_upload_removes_only_its_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            upload_path = Path(directory) / "parse-failure.pdf"
            upload = UploadFile(filename=upload_path.name, file=BytesIO(b"invalid pdf"))
            with patch.object(main, "UPLOAD_DIR", Path(directory)), patch.object(
                main, "process_upload", side_effect=ValueError("No usable content")
            ):
                with self.assertRaises(HTTPException) as raised:
                    asyncio.run(main.upload_material(upload, db=None))

            self.assertEqual(raised.exception.status_code, 400)
            self.assertFalse(upload_path.exists())

    def test_retrieval_failure_returns_service_unavailable(self) -> None:
        with patch.object(main, "_material_id_from_question", return_value=None), patch.object(
            main, "retrieve_context", side_effect=RuntimeError("index offline")
        ):
            with self.assertRaises(HTTPException) as raised:
                main.ask_question(AskRequest(question="What is durability?"), db=None)

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail, "Course retrieval is temporarily unavailable.")

    def test_cors_uses_explicit_local_origins_without_credentials(self) -> None:
        cors = next(
            middleware
            for middleware in main.app.user_middleware
            if middleware.cls is CORSMiddleware
        )
        self.assertNotIn("*", cors.kwargs["allow_origins"])
        self.assertIn("http://127.0.0.1:5173", cors.kwargs["allow_origins"])
        self.assertFalse(cors.kwargs["allow_credentials"])

    def test_fallback_embedding_is_stable_across_processes(self) -> None:
        backend_dir = Path(__file__).resolve().parents[1]
        code = (
            "import json; from app.rag.vector_store import _simple_embedding; "
            "print(json.dumps(_simple_embedding('database transaction durability').tolist()))"
        )
        output = subprocess.check_output(
            [sys.executable, "-c", code], cwd=backend_dir, text=True
        )
        self.assertEqual(
            json.loads(output), _simple_embedding("database transaction durability").tolist()
        )

    def test_pptx_extraction_and_topic_classification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dbms.pptx"
            presentation = Presentation()
            slide = presentation.slides.add_slide(presentation.slide_layouts[1])
            slide.shapes.title.text = "Transactions"
            slide.placeholders[1].text = "ACID durability protects committed changes."
            presentation.save(path)

            chunks = extract_ppt_chunks(path, path.name)

        self.assertEqual(chunks[0]["location_ref"], "Slide 1")
        self.assertEqual(chunks[0]["source_name"], "dbms.pptx")
        self.assertEqual(
            classify_topic_and_concept(chunks[0]["content"])[0],
            "Transactions and Concurrency",
        )
        self.assertEqual(detect_file_type("course.pptx"), ".pptx")
        with self.assertRaises(ValueError):
            detect_file_type("legacy.ppt")

    def test_assessment_questions_require_definition_evidence(self) -> None:
        topic = Topic(name="Transactions and Concurrency")
        self.session.add(topic)
        self.session.flush()
        chunk = ContentChunk(
            material_id=1,
            content="Lecture outline lists ACID terms: atomicity, durability, consistency, isolation.",
            source_name="outline.pdf",
            source_type="pdf",
            location_ref="Page 1",
            topic_id=topic.id,
            chunk_hash="assessment-terms-only",
        )
        self.session.add(chunk)
        self.session.commit()

        self.assertEqual(
            generate_assessment_questions(self.session, topic=topic.name, limit=5),
            [],
        )

        chunk.content = (
            "Atomicity makes a transaction all-or-nothing. Durability ensures "
            "committed changes survive system failures. Consistency enforces "
            "valid database constraints. Isolation lets concurrent transactions "
            "execute independently without interference."
        )
        self.session.commit()
        questions = generate_assessment_questions(
            self.session, topic=topic.name, limit=5
        )
        self.assertEqual(
            {question.correct_answer for question in questions},
            {"Atomicity", "Durability", "Consistency", "Isolation"},
        )
        self.assertTrue(
            all(question.source_reference == "outline.pdf | Page 1" for question in questions)
        )

    def test_prerequisite_requires_explicit_course_statement(self) -> None:
        material = Material(filename="prerequisite-source.pdf", file_type="pdf")
        self.session.add(material)
        self.session.flush()
        source_text = "ACID is a prerequisite for serializability."
        self.session.add(
            ContentChunk(
                material_id=material.id,
                content=source_text,
                source_name=material.filename,
                source_type="pdf",
                location_ref="Page 7",
                chunk_hash="explicit-prerequisite-test",
            )
        )
        self.session.flush()

        assign_explicit_prerequisites(self.session, source_text)
        self.session.flush()
        acid = self.session.query(Concept).filter_by(name="Acid").one()
        serializability = self.session.query(Concept).filter_by(name="Serializability").one()
        self.assertEqual(serializability.prerequisite_id, acid.id)

        assign_explicit_prerequisites(self.session, "ACID helps with serializability.")
        assign_explicit_prerequisites(
            self.session, "Serializability is a prerequisite for ACID."
        )
        self.session.flush()
        self.assertEqual(serializability.prerequisite_id, acid.id)
        self.assertIsNone(acid.prerequisite_id)

    def test_submission_updates_feedback_mastery_weak_topics_and_recommendation(self) -> None:
        topic = Topic(name="Transactions and Concurrency")
        material = Material(filename="course.pdf", file_type="pdf")
        self.session.add_all([topic, material])
        self.session.flush()
        concept = Concept(topic_id=topic.id, name="Durability")
        self.session.add(concept)
        self.session.flush()
        self.session.add(
            ContentChunk(
                material_id=material.id,
                content="Durability preserves committed changes after failure.",
                source_name=material.filename,
                source_type="pdf",
                location_ref="Page 4",
                topic_id=topic.id,
                concept_id=concept.id,
                chunk_hash="submission-flow-test",
            )
        )
        question = AssessmentQuestion(
            topic=topic.name,
            concept=concept.name,
            difficulty="medium",
            question_type="mcq",
            question_text="Which ACID property protects committed changes?",
            options=["Atomicity", "Durability"],
            correct_answer="Durability",
            source_reference="course.pdf | Page 4",
        )
        self.session.add(question)
        self.session.commit()

        correct = submit_assessment(
            AssessmentSubmission(question_id=question.id, student_answer="Durability"),
            self.session,
        )
        mastery_after_correct = get_mastery(self.session)[0]["mastery_score"]
        incorrect = submit_assessment(
            AssessmentSubmission(question_id=question.id, student_answer="Atomicity"),
            self.session,
        )
        mastery_after_incorrect = get_mastery(self.session)[0]["mastery_score"]

        self.assertTrue(correct.correctness)
        self.assertEqual(correct.citations[0], Citation(source_name="course.pdf", location="Page 4"))
        self.assertFalse(incorrect.correctness)
        self.assertEqual(incorrect.score, 0.0)
        self.assertIn("not supported", incorrect.source_grounded_feedback)
        self.assertIn("durability with atomicity", incorrect.misconception_detected)
        self.assertGreater(mastery_after_correct, mastery_after_incorrect)
        self.assertEqual(get_weak_topics(self.session)[0]["topic"], topic.name)
        recommendation = generate_recommendations(self.session)[0]
        self.assertEqual(recommendation["topic"], topic.name)
        self.assertEqual(recommendation["source_name"], material.filename)
        self.assertEqual(recommendation["location"], "Page 4")
        logs = self.session.query(AssessmentLog).order_by(AssessmentLog.id).all()
        self.assertEqual(len(logs), 2)
        self.assertIsNotNone(logs[1].misconception_detected)

    def test_live_evaluation_uses_supplied_model_output_without_mastery_mutation(self) -> None:
        question = AssessmentQuestion(
            topic="Transactions and Concurrency",
            concept="Durability",
            difficulty="medium",
            question_type="mcq",
            question_text="What does durability guarantee?",
            options=["Committed changes persist", "Transactions are isolated"],
            correct_answer="Committed changes persist",
            source_reference="course.pdf | Page 4",
        )
        self.session.add(question)
        self.session.commit()
        chunks = [
            {
                "content": "Committed changes persist after system failure.",
                "source_name": "course.pdf",
                "location_ref": "Page 4",
            }
        ]

        def answer_with_sources(question_text: str, topic: str, concept: str):
            answer = "Committed changes persist. [course.pdf | Page 4]"
            return AskResponse(
                answer=answer,
                supported=True,
                citations=[Citation(source_name="course.pdf", location="Page 4")],
            ), chunks

        result = run_model_evaluation(
            self.session, answer_with_sources, _citations_match_retrieved_chunks
        )
        self.assertEqual(result["cases_evaluated"], 1)
        self.assertEqual(result["supported_response_rate"], 1.0)
        self.assertEqual(result["citation_validity"], 1.0)
        self.assertGreater(result["mean_reference_token_f1"], 0.0)
        self.assertEqual(get_mastery(self.session), [])

    def test_timestamp_format_and_missing_whisper_are_explicit(self) -> None:
        self.assertEqual(
            [_format_timestamp(value) for value in (0, 59.9, 60, 3661.8)],
            ["00:00", "00:59", "01:00", "01:01:01"],
        )
        if whisper is None:
            with tempfile.TemporaryDirectory() as directory:
                video = Path(directory) / "untranscribed.mp4"
                video.write_bytes(b"")
                with self.assertRaisesRegex(RuntimeError, "Whisper is not installed"):
                    extract_video_chunks(video, video.name)

    def test_live_evaluation_provider_failure_does_not_store_metrics(self) -> None:
        self.session.add(
            AssessmentQuestion(
                topic="Transactions and Concurrency",
                concept="Durability",
                difficulty="medium",
                question_type="mcq",
                question_text="What does durability guarantee?",
                options=["Committed changes persist", "Transactions are isolated"],
                correct_answer="Committed changes persist",
                source_reference="course.pdf | Page 4",
            )
        )
        self.session.commit()
        main.app.state.evaluation_results = None

        with patch.object(main, "_answer_with_sources", side_effect=LLMError("provider unavailable")):
            with self.assertRaises(HTTPException) as raised:
                main.run_evaluation(self.session)

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIsNone(main.app.state.evaluation_results)

    def test_reference_token_f1_is_transparent(self) -> None:
        self.assertEqual(
            reference_token_f1(
                "Durability preserves committed changes",
                "Durability preserves changes",
            ),
            0.8571,
        )


if __name__ == "__main__":
    unittest.main()