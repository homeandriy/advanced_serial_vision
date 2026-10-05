from __future__ import annotations

import unittest

from serial_vision.barcode import extract_printed_codes


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


if __name__ == "__main__":
    unittest.main()
