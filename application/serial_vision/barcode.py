from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps


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
    def __init__(self, module_unavailable_message: str = "Модуль розпізнавання штрихкодів не встановлено.") -> None:
        self.module_unavailable_message = module_unavailable_message

    def recognize(self, image_path: Path) -> str:
        try:
            import zxingcpp
        except ImportError as error:
            raise RuntimeError(self.module_unavailable_message) from error

        values: list[str] = []
        with Image.open(image_path) as image:
            for variant in self._variants(image):
                results = zxingcpp.read_barcodes(
                    variant,
                    try_rotate=True,
                    try_downscale=True,
                )
                values.extend(f"{item.format.name}: {item.text}" for item in results if item.text)
        return "\n".join(dict.fromkeys(values))

    @staticmethod
    def _variants(image: Image.Image) -> tuple[Image.Image, ...]:
        original = ImageOps.exif_transpose(image).convert("RGB")
        grayscale = ImageOps.grayscale(original)
        enlarged = grayscale.resize(
            (grayscale.width * 2, grayscale.height * 2),
            Image.Resampling.LANCZOS,
        )
        enhanced = ImageEnhance.Contrast(ImageOps.autocontrast(enlarged)).enhance(2.0)
        return original, enlarged, enhanced
