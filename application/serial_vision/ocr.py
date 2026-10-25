from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image
from rapidocr import RapidOCR

from serial_vision.barcode import extract_printed_codes
from serial_vision.recognition_strategies import (
    RecognitionOptions,
    fallback_strategies,
    normalized_image,
)


class RapidOcrRecognizer:
    def __init__(self, language: str = "eng", options: RecognitionOptions | None = None) -> None:
        self.language = language
        self.options = options or RecognitionOptions()

    def recognize(self, image_path: Path) -> str:
        engine = self._engine()
        result = engine(str(image_path))
        text = self._text(result)
        best_score = self._quality(text, result)
        if (self.options.rotate or self.options.enhance) and not self._sufficient(text, result):
            with Image.open(image_path) as source:
                original = normalized_image(source)
                for strategy in fallback_strategies(self.options):
                    for variant in strategy.variants(original):
                        try:
                            candidate_result = engine(np.asarray(variant))
                        except (RuntimeError, ValueError):
                            continue
                        candidate = self._text(candidate_result)
                        quality = self._quality(candidate, candidate_result)
                        if quality > best_score:
                            text, best_score = candidate, quality
        if not text:
            raise RuntimeError("ocr_no_text")
        return text

    @staticmethod
    def _text(result: object) -> str:
        return "\n".join(value for value in (getattr(result, "txts", None) or ()) if value.strip())

    @staticmethod
    def _quality(text: str, result: object) -> float:
        scores = getattr(result, "scores", None) or ()
        confidence = sum(scores) / len(scores) if scores else 0.0
        codes = extract_printed_codes(text)
        labels = len(re.findall(r"\b(?:SN|S/N|MAC|CMAC|MODEL|P-SN|CHIP ID)\b", text, re.I))
        return len(codes) * 10 + labels * 2 + confidence + min(len(text), 300) / 300

    @staticmethod
    def _sufficient(text: str, result: object) -> bool:
        scores = getattr(result, "scores", None) or ()
        confidence = sum(scores) / len(scores) if scores else 0.0
        labels = len(re.findall(r"\b(?:SN|S/N|MAC|CMAC|MODEL|P-SN|CHIP ID)\b", text, re.I))
        return labels >= 2 and confidence >= 0.85

    @staticmethod
    @lru_cache(maxsize=1)
    def _engine() -> RapidOCR:
        return RapidOCR()

    @staticmethod
    def _score(text: str) -> int:
        return sum(
            len(value)
            for value in re.findall(r"(?:[A-Z][A-Z0-9:._-]{4,}|[0-9][A-Z0-9:._-]{4,})", text)
        )

    def _relevant(self, text: str) -> str:
        return "\n".join(line for line in text.splitlines() if self._score(line) > 0)
