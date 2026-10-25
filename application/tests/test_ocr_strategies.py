from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image
from serial_vision.ocr import RapidOcrRecognizer
from serial_vision.recognition_strategies import RecognitionOptions


class OcrStrategyTest(unittest.TestCase):
    def test_clear_original_text_is_kept_without_extra_passes(self) -> None:
        result = SimpleNamespace(
            txts=("SN: D031-2407013077", "MAC: 505B1D29F44B"), scores=(0.98, 0.98)
        )
        engine = Mock(return_value=result)
        with (
            TemporaryDirectory() as directory,
            patch.object(RapidOcrRecognizer, "_engine", return_value=engine),
        ):
            path = Path(directory) / "label.png"
            Image.new("RGB", (40, 30), "white").save(path)
            text = RapidOcrRecognizer(options=RecognitionOptions()).recognize(path)
        self.assertIn("D031-2407013077", text)
        engine.assert_called_once_with(str(path))

    def test_rotated_candidate_can_recover_weak_original(self) -> None:
        weak = SimpleNamespace(txts=("unclear",), scores=(0.3,))
        recovered = SimpleNamespace(
            txts=("SN: D031-2407013077", "MAC: 505B1D29F44B"), scores=(0.98, 0.98)
        )
        engine = Mock(side_effect=[weak, recovered, weak, weak])
        with (
            TemporaryDirectory() as directory,
            patch.object(RapidOcrRecognizer, "_engine", return_value=engine),
        ):
            path = Path(directory) / "label.png"
            Image.new("RGB", (40, 30), "white").save(path)
            text = RapidOcrRecognizer(
                options=RecognitionOptions(rotate=True, enhance=False)
            ).recognize(path)
        self.assertIn("505B1D29F44B", text)
        self.assertEqual(4, engine.call_count)


if __name__ == "__main__":
    unittest.main()
