from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from serial_vision.updates import ReleaseInfo, _download_asset, check_latest_release, create_update_log, download_linux_update, download_update, launch_update, prune_update_logs


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class _DownloadResponse:
    headers = {"Content-Length": "6"}

    def __init__(self) -> None:
        self.chunks = iter((b"abc", b"def", b""))

    def __enter__(self) -> "_DownloadResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _size: int) -> bytes:
        return next(self.chunks)


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

    @patch("serial_vision.updates.urllib.request.urlopen")
    def test_reports_asset_download_progress_and_verification(self, urlopen) -> None:
        urlopen.return_value = _DownloadResponse()
        progress: list[tuple[int, int | None, str]] = []
        phases: list[str] = []
        with TemporaryDirectory() as directory:
            path = _download_asset("https://example.test/update.exe", "bef57ec7f53a6d40beb640a780a639c83bc29ac8a9816f1fc6c5c6dcd93c4721", Path(directory), lambda downloaded, total, url: progress.append((downloaded, total, url)), phases.append)
            self.assertEqual(b"abcdef", path.read_bytes())

        self.assertEqual([(3, 6, "https://example.test/update.exe"), (6, 6, "https://example.test/update.exe")], progress)
        self.assertEqual(["verifying"], phases)

    def test_update_logs_are_created_and_old_logs_are_pruned(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            logs = root / "update-logs"
            logs.mkdir()
            old = logs / "old.log"
            old.write_text("old", encoding="utf-8")
            os.utime(old, (0, 0))

            path = create_update_log(root)

            self.assertTrue(path.is_file())
            self.assertIn("Update session started.", path.read_text(encoding="utf-8"))
            self.assertFalse(old.exists())
            prune_update_logs(logs)

    @patch("serial_vision.updates.subprocess.Popen")
    @patch("serial_vision.updates.sys")
    def test_starts_visible_installer_without_locking_the_application_executable(self, mock_sys, popen) -> None:
        mock_sys.platform = "win32"
        mock_sys.frozen = True
        installer = Path("C:/temporary/SerialVision-Setup-v0.6.2.exe")
        log = Path("C:/temporary/update.log")

        launch_update(installer, log)

        popen.assert_called_once_with(
            [str(installer), "/CLOSEAPPLICATIONS", "/NORESTART", f"/LOG={log}"],
            close_fds=True,
        )
