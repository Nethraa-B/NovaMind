from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False, unique=True, index=True)
    file_type = Column(String(50), nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    chunks = relationship("ContentChunk", back_populates="material", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, default="")

    concepts = relationship("Concept", back_populates="topic", cascade="all, delete-orphan")
    mastery = relationship("LearnerMastery", back_populates="topic", cascade="all, delete-orphan")
    chunks = relationship("ContentChunk", back_populates="topic")


class Concept(Base):
    __tablename__ = "concepts"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    prerequisite_id = Column(Integer, ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True)

    topic = relationship("Topic", back_populates="concepts")
    prerequisite = relationship("Concept", remote_side="Concept.id")
    chunks = relationship("ContentChunk", back_populates="concept")

    __table_args__ = (UniqueConstraint("topic_id", "name", name="uq_topic_concept_name"),)


class ContentChunk(Base):
    __tablename__ = "content_chunks"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    source_name = Column(String(255), nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True)
    location_ref = Column(String(255), nullable=False, default="Unknown")
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    concept_id = Column(Integer, ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True, index=True)
    chunk_hash = Column(String(128), nullable=False, index=True)

    material = relationship("Material", back_populates="chunks")
    topic = relationship("Topic", back_populates="chunks")
    concept = relationship("Concept", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("material_id", "chunk_hash", name="uq_chunk_material_hash"),
        Index("idx_content_chunk_material_topic", "material_id", "topic_id"),
    )


class LearnerMastery(Base):
    __tablename__ = "learner_mastery"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    mastery_score = Column(Float, nullable=False, default=50.0)
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)

    topic = relationship("Topic", back_populates="mastery")


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(255), nullable=False, index=True)
    concept = Column(String(255), nullable=False, index=True)
    difficulty = Column(String(50), nullable=False, default="medium")
    question_type = Column(String(50), nullable=False, default="mcq")
    question_text = Column(Text, nullable=False)
    options = Column(JSON, nullable=True)
    correct_answer = Column(Text, nullable=False)
    source_reference = Column(String(255), nullable=False)

    logs = relationship("AssessmentLog", back_populates="question", cascade="all, delete-orphan")


class AssessmentLog(Base):
    __tablename__ = "assessment_logs"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("assessment_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_answer = Column(Text, nullable=False)
    is_correct = Column(Integer, nullable=False, default=0)
    misconception_detected = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    question = relationship("AssessmentQuestion", back_populates="logs")
