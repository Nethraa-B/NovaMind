from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models import LearnerMastery, Topic


def ensure_topic_mastery(db: Session, topic_name: str) -> LearnerMastery:
    topic = db.query(Topic).filter(Topic.name == topic_name).first()
    if not topic:
        topic = Topic(name=topic_name, description=f"Content related to {topic_name}.")
        db.add(topic)
        db.flush()

    mastery = db.query(LearnerMastery).filter(LearnerMastery.topic_id == topic.id).first()
    if mastery is None:
        mastery = LearnerMastery(topic_id=topic.id, mastery_score=50.0, last_updated=datetime.utcnow())
        db.add(mastery)
        db.flush()
    return mastery


def update_mastery(db: Session, topic_name: str, score: float, difficulty: str = "medium", repeated_errors: int = 0) -> LearnerMastery:
    mastery = ensure_topic_mastery(db, topic_name)
    previous = float(mastery.mastery_score)
    difficulty_weight = {"easy": 0.12, "medium": 0.18, "hard": 0.22}.get((difficulty or "medium").lower(), 0.18)
    repeated_penalty = max(0.0, repeated_errors * 2.5)
    if score >= 0.8:
        delta = 8.0 * (score - 0.5) + difficulty_weight * 8.0 - repeated_penalty * 0.3
    elif score >= 0.5:
        delta = 5.0 * (score - 0.5) + difficulty_weight * 2.5 - repeated_penalty * 0.2
    else:
        delta = -7.0 * (0.8 - score) - repeated_penalty * 0.5

    new_score = max(0.0, min(100.0, previous + delta))
    mastery.mastery_score = round(new_score, 2)
    mastery.last_updated = datetime.utcnow()
    db.add(mastery)
    db.commit()
    db.refresh(mastery)
    return mastery


def get_mastery(db: Session) -> List[Dict[str, Any]]:
    rows = db.query(LearnerMastery).join(Topic).order_by(Topic.name.asc()).all()
    return [
        {
            "topic": row.topic.name,
            "mastery_score": round(float(row.mastery_score), 2),
            "last_updated": row.last_updated.isoformat(),
        }
        for row in rows
    ]


def get_weak_topics(db: Session, limit: int = 5) -> List[Dict[str, Any]]:
    rows = db.query(LearnerMastery).join(Topic).order_by(LearnerMastery.mastery_score.asc(), Topic.name.asc()).limit(limit).all()
    return [
        {
            "topic": row.topic.name,
            "mastery_score": round(float(row.mastery_score), 2),
        }
        for row in rows
    ]
