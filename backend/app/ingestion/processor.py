from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.database import SessionLocal
from app.models import Concept, ContentChunk, Material, Topic

from .pdf_processor import extract_pdf_chunks
from .ppt_processor import extract_ppt_chunks
from .video_processor import extract_video_chunks

SUPPORTED_EXTENSIONS = {
    ".pdf": extract_pdf_chunks,
    ".pptx": extract_ppt_chunks,
    ".mp4": extract_video_chunks,
}

TOPIC_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    "Transactions and Concurrency": {
        "concept": ["transaction", "acid", "isolation", "serializability", "lock", "deadlock", "concurrency"],
        "fallback": ["transaction processing"],
    },
    "SQL and Query Processing": {
        "concept": ["sql", "join", "select", "where", "group by", "primary key", "foreign key", "query"] ,
        "fallback": ["query processing"],
    },
    "Storage and Indexing": {
        "concept": ["index", "b-tree", "hash index", "storage", "buffer", "page", "heap file"],
        "fallback": ["indexing"],
    },
    "Normalization and Design": {
        "concept": ["normalization", "functional dependency", "1nf", "2nf", "3nf", "entity relationship", "schema"],
        "fallback": ["database design"],
    },
    "Recovery and Security": {
        "concept": ["recovery", "log", "backup", "rollback", "security", "authorization", "audit"],
        "fallback": ["recovery"]
    },
}

_CONCEPT_TOPICS = {
    term: topic_name
    for topic_name, metadata in TOPIC_KEYWORDS.items()
    for term in metadata["concept"] + metadata["fallback"]
}
_CONCEPT_PATTERN = "|".join(re.escape(term) for term in sorted(_CONCEPT_TOPICS, key=len, reverse=True))
_EXPLICIT_PREREQUISITE = re.compile(
    rf"(?<!\w)(?P<prerequisite>{_CONCEPT_PATTERN})(?!\w)\s+(?:is|are)\s+(?:a\s+)?prerequisite\s+for\s+(?P<dependent>{_CONCEPT_PATTERN})(?!\w)",
    flags=re.IGNORECASE,
)


def detect_file_type(filename: str) -> str:
    normalized = Path(filename).suffix.lower()
    if normalized not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {filename}. Supported types: PDF, PPTX, MP4.")
    return normalized


def _normalize_chunk_text(text: str) -> str:
    return " ".join(text.split()).strip()


def _hash_chunk(content: str, source_name: str, location_ref: str) -> str:
    payload = f"{content}|{source_name}|{location_ref}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def classify_topic_and_concept(text: str) -> Tuple[str, str]:
    lower = text.lower()
    for topic_name, metadata in TOPIC_KEYWORDS.items():
        keywords = metadata["concept"] + metadata["fallback"]
        if any(keyword in lower for keyword in keywords):
            concept_name = next((keyword for keyword in metadata["concept"] if keyword in lower), metadata["fallback"][0])
            return topic_name, concept_name.title()
    return "Uncategorized", "General Course Content"


def ensure_topic_and_concept(db: Session, topic_name: str, concept_name: str) -> Tuple[Topic, Concept]:
    topic = db.query(Topic).filter(Topic.name == topic_name).first()
    if not topic:
        topic = Topic(name=topic_name, description=f"Content related to {topic_name}.")
        db.add(topic)
        db.flush()

    concept = db.query(Concept).filter(Concept.topic_id == topic.id, Concept.name == concept_name).first()
    if not concept:
        concept = Concept(topic_id=topic.id, name=concept_name, prerequisite_id=None)
        db.add(concept)
        db.flush()

    return topic, concept


def assign_explicit_prerequisites(db: Session, content: str) -> None:
    for match in _EXPLICIT_PREREQUISITE.finditer(content):
        prerequisite_term = match.group("prerequisite").lower()
        dependent_term = match.group("dependent").lower()
        prerequisite_topic, prerequisite = ensure_topic_and_concept(
            db, _CONCEPT_TOPICS[prerequisite_term], prerequisite_term.title()
        )
        dependent_topic, dependent = ensure_topic_and_concept(
            db, _CONCEPT_TOPICS[dependent_term], dependent_term.title()
        )
        if prerequisite.id == dependent.id or dependent.prerequisite_id is not None:
            continue

        cursor = prerequisite
        visited = set()
        creates_cycle = False
        while cursor is not None and cursor.id not in visited:
            if cursor.id == dependent.id:
                creates_cycle = True
                break
            visited.add(cursor.id)
            cursor = cursor.prerequisite

        if not creates_cycle:
            dependent.prerequisite = prerequisite
            db.add(dependent)


def extract_file_chunks(file_name: str, file_path: str) -> List[Dict[str, Any]]:
    ext = detect_file_type(file_name)
    extractor = SUPPORTED_EXTENSIONS[ext]
    chunks = extractor(file_path, file_name)
    cleaned: List[Dict[str, Any]] = []
    for item in chunks:
        content = _normalize_chunk_text(str(item.get("content", "")))
        if not content:
            continue
        cleaned.append(
            {
                "content": content,
                "source_name": item.get("source_name", file_name),
                "source_type": item.get("source_type", ext.lstrip(".")),
                "location_ref": item.get("location_ref", "N/A"),
            }
        )
    return cleaned


def process_upload(file_name: str, file_path: str) -> Material:
    db = SessionLocal()
    try:
        if not file_name or not os.path.exists(file_path):
            raise ValueError("Uploaded file is missing or invalid.")

        existing = db.query(Material).filter(Material.filename == file_name).first()
        if existing:
            raise ValueError(f"Duplicate upload detected for {file_name}. The file already exists in the course library.")

        file_type = detect_file_type(file_name)
        material = Material(filename=file_name, file_type=file_type.lstrip("."))
        db.add(material)
        db.flush()

        chunks = extract_file_chunks(file_name, file_path)

        if not chunks:
            db.delete(material)
            db.commit()
            raise ValueError(f"No usable content could be extracted from {file_name}.")

        for chunk_dict in chunks:
            topic_name, concept_name = classify_topic_and_concept(chunk_dict["content"])
            topic, concept = ensure_topic_and_concept(db, topic_name, concept_name)
            chunk_hash = _hash_chunk(chunk_dict["content"], chunk_dict["source_name"], chunk_dict["location_ref"])
            existing_chunk = db.query(ContentChunk).filter(ContentChunk.material_id == material.id, ContentChunk.chunk_hash == chunk_hash).first()
            if existing_chunk:
                continue

            chunk = ContentChunk(
                material_id=material.id,
                content=chunk_dict["content"],
                source_name=chunk_dict["source_name"],
                source_type=chunk_dict["source_type"],
                location_ref=chunk_dict["location_ref"],
                topic_id=topic.id,
                concept_id=concept.id,
                chunk_hash=chunk_hash,
            )
            db.add(chunk)

        for chunk_dict in chunks:
            assign_explicit_prerequisites(db, chunk_dict["content"])

        db.commit()
        db.refresh(material)
        return material
    finally:
        db.close()
