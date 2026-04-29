from __future__ import annotations

from pathlib import Path

from PIL import Image


def extract_text_with_tesseract(image_paths: list[str | Path]) -> str:
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("pytesseract is not installed. Install it and the Tesseract app to OCR images.") from exc

    chunks: list[str] = []
    for path in image_paths:
        image = Image.open(path)
        chunks.append(pytesseract.image_to_string(image))
    return "\n\n".join(chunks)
