from __future__ import annotations

from datetime import datetime
import unittest

from serial_vision.code_images import generated_code_filename, generate_code_png


class CodeImagesTest(unittest.TestCase):
    def test_generates_qr_and_code128_png(self) -> None:
        for code_type in ("qr", "barcode"):
            image = generate_code_png("AA:BB:CC:DD:EE:FF", code_type)
            self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_requires_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "code_value_empty"):
            generate_code_png("  ", "qr")

    def test_filename_is_sanitized_and_stable(self) -> None:
        name = generated_code_filename("AA:BB-CC DD", "qr", datetime(2026, 8, 27, 0, 34))
        self.assertEqual("qrcode_AABBCCDD_00_34_27_08_2026.png", name)


if __name__ == "__main__":
    unittest.main()
