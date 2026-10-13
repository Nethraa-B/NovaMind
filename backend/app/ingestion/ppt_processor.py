from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

try:
    from pptx import Presentation
except ImportError:  # pragma: no cover - optional dependency
    Presentation = None


def extract_ppt_chunks(file_path: str | Path, source_name: str) -> List[Dict[str, Any]]:
    if Presentation is None:
        raise RuntimeError("python-pptx is not installed. Install it to process PPT/PPTX uploads.")
    ppt_path = Path(file_path)
    if not ppt_path.exists():
        raise FileNotFoundError(f"PowerPoint file not found: {ppt_path}")

    presentation = Presentation(str(ppt_path))
    chunks: List[Dict[str, Any]] = []

    for slide_number, slide in enumerate(presentation.slides, start=1):
        texts = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                texts.append(shape.text.strip())

        content = " ".join(texts)
        if content.strip():
            chunks.append(
                {
                    "content": " ".join(content.split()),
                    "source_name": source_name,
                    "source_type": "pptx",
                    "location_ref": f"Slide {slide_number}",
                }
            )

        if slide.shapes:
            figure_present = any(shape.is_placeholder and shape.placeholder_format.type in {13, 14, 15, 16} for shape in slide.shapes)
            if figure_present:
                chunks.append(
                    {
                        "content": f"Diagram or figure on Slide {slide_number}; the source contains an embedded visual and should be reviewed in context.",
                        "source_name": source_name,
                        "source_type": "pptx",
                        "location_ref": f"Slide {slide_number}",
                    }
                )

    return chunks
