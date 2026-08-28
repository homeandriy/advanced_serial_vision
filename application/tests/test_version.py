from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from serial_vision.version import app_version


class VersionTest(unittest.TestCase):
    def test_reads_project_version_outside_project_working_directory(self) -> None:
        expected = (Path(__file__).resolve().parents[2] / "VERSION").read_text(encoding="utf-8").strip()
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)
            try:
                self.assertEqual(expected, app_version())
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
