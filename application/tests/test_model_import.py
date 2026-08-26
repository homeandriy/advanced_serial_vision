from __future__ import annotations

import unittest

from serial_vision.model_import import _parse_rows


class ModelImportTest(unittest.TestCase):
    def test_accepts_supported_models_and_reports_invalid_rows(self) -> None:
        result = _parse_rows(
            [
                ["name", "device_type", "service"],
                ["Arris CM820", "modem", "internet"],
                ["Bad model", "router", "internet"],
                ["", "tuner", "television"],
            ]
        )

        self.assertEqual(1, len(result.models))
        self.assertEqual("Arris CM820", result.models[0].name)
        self.assertEqual("modem", result.models[0].device_type)
        self.assertEqual("internet", result.models[0].service)
        self.assertEqual(["3", "4"], result.errors)


if __name__ == "__main__":
    unittest.main()
