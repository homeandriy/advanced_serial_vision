from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from serial_vision.updates import check_latest_release


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class UpdateTests(unittest.TestCase):
    @patch("serial_vision.updates.urllib.request.urlopen")
    def test_uses_release_installer_and_sha256_digest(self, urlopen) -> None:
        urlopen.return_value = _Response({
            "tag_name": "v0.2.8",
            "body": "Update",
            "assets": [{
                "name": "SerialVision-Setup-v0.2.8.exe",
                "browser_download_url": "https://example.test/SerialVision-Setup-v0.2.8.exe",
                "digest": "sha256:abc123",
            }],
        })

        release = check_latest_release("homeandriy/advanced_serial_vision", "0.2.0")

        self.assertIsNotNone(release)
        assert release is not None
        self.assertEqual("0.2.8", release.version)
        self.assertEqual("https://example.test/SerialVision-Setup-v0.2.8.exe", release.installer_url)
        self.assertEqual("abc123", release.installer_sha256)

    @patch("serial_vision.updates.urllib.request.urlopen")
    def test_ignores_current_or_older_release(self, urlopen) -> None:
        urlopen.return_value = _Response({"tag_name": "v0.2.0", "assets": []})

        self.assertIsNone(check_latest_release("homeandriy/advanced_serial_vision", "0.2.0"))
