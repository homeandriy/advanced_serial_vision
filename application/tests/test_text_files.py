from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TextFilesCheckTest(unittest.TestCase):
    script = Path(__file__).resolve().parents[2] / "scripts" / "check_text_files.py"

    def test_staged_check_reads_index_and_rejects_bad_text_but_accepts_binary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*arguments, data=None):
                return subprocess.check_output(["git", *arguments], cwd=root, input=data)

            git("init", "-q")
            (root / ".gitattributes").write_bytes(b"*.py text eol=lf\n*.png -text\n")
            (root / "good.py").write_bytes(b"value = 1\n")
            (root / "image.png").write_bytes(b"\xff\x00\r\n\xff")
            git("add", ".")
            # An unstaged CRLF edit must not make the valid index fail.
            (root / "good.py").write_bytes(b"value = 2\r\n")
            command = [sys.executable, str(self.script), "--staged"]
            result = subprocess.run(command, cwd=root, capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            for bad in (
                b"value = 1\r\n",
                b"\xef\xbb\xbfvalue = 1\n",
                b"# \xff\n",
                b"v\x00a\x00l\x00u\x00e\x00",
            ):
                with self.subTest(contents=bad):
                    oid = git("hash-object", "-w", "--stdin", data=bad).decode().strip()
                    git("update-index", "--add", "--cacheinfo", f"100644,{oid},good.py")
                    result = subprocess.run(command, cwd=root, capture_output=True, text=True)
                    self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                    self.assertIn("good.py:", result.stdout)
