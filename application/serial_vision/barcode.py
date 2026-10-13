from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

from serial_vision.recognition_strategies import OriginalStrategy, RecognitionOptions, fallback_strategies, normalized_image


_PRINTED_CODE_PATTERNS = (
    re.compile(r"(?<![A-Z0-9])(?:[0-9A-F]{2}){6}(?![A-Z0-9])"),
    re.compile(r"(?<![A-Z0-9])D[0-9]{3}-[0-9]{10}(?![A-Z0-9])"),
    re.compile(r"(?<![A-Z0-9])HWT[A-Z0-9]{9}(?![A-Z0-9])"),
    re.compile(r"(?<![A-Z0-9])TV[0-9]{9}(?![A-Z0-9])"),
)


def extract_printed_codes(text: str) -> list[str]:
    """Extract serial and MAC-like values printed below a barcode."""
    values: list[str] = []
    normalized = text.upper()
    normalized = re.sub(r"(?<=[:\s])I(?=TV[0-9]{9}(?![A-Z0-9]))", "", normalized)
    for pattern in _PRINTED_CODE_PATTERNS:
        values.extend(match.group(0) for match in pattern.finditer(normalized))
    return list(dict.fromkeys(values))


class BarcodeRecognizer:
    def __init__(self, module_unavailable_message: str = "Модуль розпізнавання штрихкодів не встановлено.", options: RecognitionOptions | None = None) -> None:
        self.module_unavailable_message = module_unavailable_message
        self.options = options or RecognitionOptions()

    def recognize(self, image_path: Path) -> str:
        try:
            import zxingcpp
        except ImportError as error:
            raise RuntimeError(self.module_unavailable_message) from error

        with Image.open(image_path) as image:
            original = normalized_image(image)
            strategies = (OriginalStrategy(), *fallback_strategies(self.options))
            for strategy in strategies:
                for variant in strategy.variants(original):
                    try:
                        results = zxingcpp.read_barcodes(variant)
                    except (RuntimeError, ValueError):
                        if isinstance(strategy, OriginalStrategy):
                            raise
                        continue
                    values = [f"{item.format.name}: {item.text}" for item in results if item.text]
                    if values:
                        return "\n".join(dict.fromkeys(values))
        return ""
