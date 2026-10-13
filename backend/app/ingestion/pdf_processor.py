from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any

try:
    import fitz
except ImportError:  # pragma: no cover - optional dependency
    fitz = None


def extract_pdf_chunks(file_path: str | Path, source_name: str) -> List[Dict[str, Any]]:
    if fitz is None:
        raise RuntimeError("PyMuPDF is not installed. Install it to process PDF uploads.")
    pdf_path = Path(file_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    chunks: List[Dict[str, Any]] = []
    document = fitz.open(str(pdf_path))
    try:
        for page_number in range(document.page_count):
            page = document[page_number]
            text = page.get_text("text")
            cleaned = " ".join(text.split())
            if cleaned:
                chunks.append(
                    {
                        "content": cleaned,
                        "source_name": source_name,
                        "source_type": "pdf",
                        "location_ref": f"Page {page_number + 1}",
                    }
                )

            image_count = len(page.get_images(full=True))
            if image_count:
                chunks.append(
                    {
                        "content": f"Embedded figure(s) present on Page {page_number + 1}. Textual description is not available in the source; review the image in the original file.",
                        "source_name": source_name,
                        "source_type": "pdf",
                        "location_ref": f"Page {page_number + 1}",
                    }
                )
    finally:
        document.close()

    return chunks
