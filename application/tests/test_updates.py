from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from serial_vision.updates import ReleaseInfo, check_latest_release, download_linux_update, download_update


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
            "html_url": "https://example.test/releases/tag/v0.2.8",
            "assets": [{
                "name": "SerialVision-Setup-v0.2.8.exe",
                "browser_download_url": "https://example.test/SerialVision-Setup-v0.2.8.exe",
                "digest": "sha256:abc123",
            }, {
                "name": "serial-vision_0.2.8_amd64.deb",
                "browser_download_url": "https://example.test/serial-vision_0.2.8_amd64.deb",
                "digest": "sha256:def456",
            }],
        })

        release = check_latest_release("homeandriy/advanced_serial_vision", "0.2.0")

        self.assertIsNotNone(release)
        assert release is not None
        self.assertEqual("0.2.8", release.version)
        self.assertEqual("https://example.test/SerialVision-Setup-v0.2.8.exe", release.installer_url)
        self.assertEqual("abc123", release.installer_sha256)
        self.assertEqual("https://example.test/releases/tag/v0.2.8", release.release_url)
        self.assertEqual("https://example.test/serial-vision_0.2.8_amd64.deb", release.linux_package_url)
        self.assertEqual("def456", release.linux_package_sha256)

    @patch("serial_vision.updates._download_installer")
    def test_downloads_verified_installer_before_apply(self, download_installer) -> None:
        installer = Path("C:/temporary/SerialVision-Setup-v0.5.6.exe")
        download_installer.return_value = installer
        release = ReleaseInfo("0.5.6", "Update", "https://example.test/SerialVision-Setup-v0.5.6.exe", "abc123")

        self.assertEqual(installer, download_update(release))
        download_installer.assert_called_once_with(release.installer_url, "abc123")

    @patch("serial_vision.updates._download_package")
    def test_downloads_verified_linux_package(self, download_package) -> None:
        package = Path("/home/user/Downloads/serial-vision_0.5.6_amd64.deb")
        download_package.return_value = package
        release = ReleaseInfo(
            "0.5.6", "Update", None, release_url="https://example.test/release",
            linux_package_url="https://example.test/serial-vision_0.5.6_amd64.deb", linux_package_sha256="abc123",
        )

        self.assertEqual(package, download_linux_update(release))
        download_package.assert_called_once_with(release.linux_package_url, "abc123", unittest.mock.ANY)

    @patch("serial_vision.updates.urllib.request.urlopen")
    def test_ignores_current_or_older_release(self, urlopen) -> None:
        urlopen.return_value = _Response({"tag_name": "v0.2.0", "assets": []})

        self.assertIsNone(check_latest_release("homeandriy/advanced_serial_vision", "0.2.0"))
