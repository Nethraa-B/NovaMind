from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


try:
    import whisper
except ImportError:  # pragma: no cover - optional dependency
    whisper = None


def _format_timestamp(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def extract_video_chunks(file_path: str | Path, source_name: str) -> List[Dict[str, Any]]:
    video_path = Path(file_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if whisper is None:
        raise RuntimeError("Whisper is not installed. Video transcription is optional and unavailable in this environment.")

    model = whisper.load_model("base")
    result = model.transcribe(str(video_path), fp16=False)
    chunks: List[Dict[str, Any]] = []

    for segment in result.get("segments", []):
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        start = segment.get("start", 0)
        end = segment.get("end", start)
        chunks.append(
            {
                "content": text,
                "source_name": source_name,
                "source_type": "mp4",
                "location_ref": f"{_format_timestamp(start)}-{_format_timestamp(end)}",
            }
        )

    if not chunks:
        raise RuntimeError(f"Video transcription for {source_name} produced no usable text.")

    return chunks
