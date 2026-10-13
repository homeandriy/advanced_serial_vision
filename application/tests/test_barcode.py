from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from serial_vision.barcode import BarcodeRecognizer, extract_printed_codes
from serial_vision.recognition_strategies import RecognitionOptions


class BarcodeTextFallbackTest(unittest.TestCase):
    def test_extracts_common_equipment_label_codes(self) -> None:
        text = """MAC: 505B1D29F44B
SN: D031-2407013077
P-SN: HWTC1D29F44B
SN: TV524413228"""

        self.assertEqual(
            ["505B1D29F44B", "D031-2407013077", "HWTC1D29F44B", "TV524413228"],
            extract_printed_codes(text),
        )

    def test_original_result_wins_before_fallback_strategies(self) -> None:
        result = SimpleNamespace(format=SimpleNamespace(name="Code128"), text="SERIAL123")
        reader = SimpleNamespace(read_barcodes=Mock(return_value=[result]))
        with TemporaryDirectory() as directory, patch.dict("sys.modules", {"zxingcpp": reader}):
            path = Path(directory) / "label.png"
            Image.new("RGB", (40, 30), "white").save(path)
            value = BarcodeRecognizer(options=RecognitionOptions()).recognize(path)
        self.assertEqual("Code128: SERIAL123", value)
        reader.read_barcodes.assert_called_once()

    def test_rotation_is_used_when_original_has_no_code(self) -> None:
        result = SimpleNamespace(format=SimpleNamespace(name="Code128"), text="SERIAL123")
        reader = SimpleNamespace(read_barcodes=Mock(side_effect=[[], [result]]))
        with TemporaryDirectory() as directory, patch.dict("sys.modules", {"zxingcpp": reader}):
            path = Path(directory) / "label.png"
            Image.new("RGB", (40, 30), "white").save(path)
            value = BarcodeRecognizer(options=RecognitionOptions(rotate=True, enhance=False)).recognize(path)
        self.assertEqual("Code128: SERIAL123", value)
        self.assertEqual(2, reader.read_barcodes.call_count)

    def test_can_disable_extra_strategies(self) -> None:
        reader = SimpleNamespace(read_barcodes=Mock(return_value=[]))
        with TemporaryDirectory() as directory, patch.dict("sys.modules", {"zxingcpp": reader}):
            path = Path(directory) / "label.png"
            Image.new("RGB", (40, 30), "white").save(path)
            value = BarcodeRecognizer(options=RecognitionOptions(rotate=False, enhance=False)).recognize(path)
        self.assertEqual("", value)
        reader.read_barcodes.assert_called_once()


if __name__ == "__main__":
    unittest.main()
