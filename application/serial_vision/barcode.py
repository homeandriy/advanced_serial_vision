from __future__ import annotations

from pathlib import Path
from PIL import Image


class BarcodeRecognizer:
    def recognize(self, image_path: Path) -> str:
        try:
            import zxingcpp
        except ImportError as error:
            raise RuntimeError("Модуль розпізнавання штрихкодів не встановлено.") from error
        with Image.open(image_path) as image:
            results = zxingcpp.read_barcodes(image.convert("RGB"))
        values = [f"{item.format.name}: {item.text}" for item in results if item.text]
        return "\n".join(dict.fromkeys(values))
