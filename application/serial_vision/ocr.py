from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from rapidocr import RapidOCR


class TesseractRecognizer:
    def __init__(self, binary: str = "", languages: str = "eng", psm: int = 6) -> None:
        self.binary = binary.strip() or "tesseract"
        self.languages = languages
        self.psm = psm

    def recognize(self, image_path: Path) -> str:
        result = self._engine()(str(image_path))
        text = "\n".join(value for value in result.txts if value.strip())
        if not text:
            raise RuntimeError("OCR не знайшов текст на цьому зображенні.")
        return text

    @staticmethod
    @lru_cache(maxsize=1)
    def _engine() -> RapidOCR:
        return RapidOCR()

    @staticmethod
    def _score(text: str) -> int:
        return sum(len(value) for value in re.findall(r"(?:[A-Z][A-Z0-9:._-]{4,}|[0-9][A-Z0-9:._-]{4,})", text))

    def _relevant(self, text: str) -> str:
        return "\n".join(line for line in text.splitlines() if self._score(line) > 0)
