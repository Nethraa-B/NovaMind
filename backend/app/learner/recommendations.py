from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models import ContentChunk, Topic
from app.learner.mastery import get_weak_topics


def generate_recommendations(db: Session) -> List[Dict[str, Any]]:
    weak_topics = get_weak_topics(db, limit=3)
    recommendations: List[Dict[str, Any]] = []
    for item in weak_topics:
        topic_name = item["topic"]
        topic = db.query(Topic).filter(Topic.name == topic_name).first()
        if not topic:
            continue
        chunk = db.query(ContentChunk).filter(ContentChunk.topic_id == topic.id).order_by(ContentChunk.id.asc()).first()
        recommendations.append(
            {
                "title": f"Revise {topic_name}",
                "recommendation_type": "review_concept",
                "topic": topic_name,
                "detail": f"Review the course material for {topic_name} and practice a short diagnostic assessment before attempting a harder question.",
                "source_name": chunk.source_name if chunk else None,
                "location": chunk.location_ref if chunk else None,
            }
        )
    return recommendations
