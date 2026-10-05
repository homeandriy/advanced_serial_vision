from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    changelog: str
    installer_url: str | None
    installer_sha256: str | None = None
    release_url: str | None = None
    linux_package_url: str | None = None
    linux_package_sha256: str | None = None


def check_latest_release(repository: str, current_version: str) -> ReleaseInfo | None:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Serial-Vision"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))

    version = str(payload.get("tag_name", "")).lstrip("v")
    if not version or not _is_newer(version, current_version):
        return None
    installer_asset = next(
        (asset for asset in payload.get("assets", []) if str(asset.get("name", "")).lower().endswith(".exe")),
        None,
    )
    linux_asset = next(
        (asset for asset in payload.get("assets", []) if str(asset.get("name", "")).lower().endswith(".deb")),
        None,
    )
    return ReleaseInfo(
        version,
        str(payload.get("body", "")),
        _asset_url(installer_asset),
        _asset_digest(installer_asset),
        str(payload.get("html_url", "")) or None,
        _asset_url(linux_asset),
        _asset_digest(linux_asset),
    )


def download_update(release: ReleaseInfo) -> Path:
    if not release.installer_url:
        raise RuntimeError("automatic_update_unsupported")
    return _download_installer(release.installer_url, release.installer_sha256 or "")


def download_linux_update(release: ReleaseInfo) -> Path:
    if not release.linux_package_url:
        raise RuntimeError("linux_update_unavailable")
    downloads_directory = Path.home() / "Downloads"
    destination_directory = downloads_directory if downloads_directory.is_dir() else None
    return _download_package(release.linux_package_url, release.linux_package_sha256 or "", destination_directory)


def launch_update(installer_path: Path, parent_pid: int, application_path: str) -> None:
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        raise RuntimeError("automatic_update_unsupported")
    subprocess.Popen(
        [sys.executable, "--apply-update", str(installer_path), str(parent_pid), application_path],
        close_fds=True,
    )


def apply_update(installer_path: str, parent_pid: int, application_path: str) -> int:
    if sys.platform != "win32" or not Path(installer_path).is_file():
        return 1
    _wait_for_process(parent_pid)
    installer = subprocess.Popen(
        [installer_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
        close_fds=True,
    )
    if installer.wait() != 0:
        return 1
    subprocess.Popen([application_path], close_fds=True)
    return 0


def _download_installer(url: str, expected_sha256: str) -> Path:
    return _download_asset(url, expected_sha256)


def _download_package(url: str, expected_sha256: str, destination_directory: Path | None = None) -> Path:
    return _download_asset(url, expected_sha256, destination_directory)


def _download_asset(url: str, expected_sha256: str, destination_directory: Path | None = None) -> Path:
    destination_directory = destination_directory or Path(tempfile.gettempdir()) / "serial-vision-update"
    destination_directory.mkdir(parents=True, exist_ok=True)
    filename = Path(url.split("?", 1)[0]).name or "SerialVision-Setup.exe"
    destination = destination_directory / filename
    request = urllib.request.Request(url, headers={"User-Agent": "Serial-Vision"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as target:
        while chunk := response.read(1024 * 1024):
            target.write(chunk)
            digest.update(chunk)
    if expected_sha256 and digest.hexdigest().lower() != expected_sha256.lower():
        destination.unlink(missing_ok=True)
        raise RuntimeError("update_integrity_failed")
    return destination


def _asset_url(asset: object | None) -> str | None:
    if not isinstance(asset, dict):
        return None
    url = str(asset.get("browser_download_url", ""))
    return url or None


def _asset_digest(asset: object | None) -> str | None:
    if not isinstance(asset, dict):
        return None
    digest = str(asset.get("digest", ""))
    return digest.removeprefix("sha256:") if digest.startswith("sha256:") else None


def _wait_for_process(process_id: int) -> None:
    if process_id <= 0:
        return
    import ctypes

    synchronize = 0x00100000
    handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, process_id)
    if handle:
        try:
            ctypes.windll.kernel32.WaitForSingleObject(handle, 120_000)
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)


def _is_newer(candidate: str, current: str) -> bool:
    def normalize(value: str) -> tuple[int, ...]:
        return tuple(int(part) for part in re.findall(r"\d+", value)[:3])

    return normalize(candidate) > normalize(current)
