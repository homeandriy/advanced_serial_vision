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
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable


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


ProgressCallback = Callable[[int, int | None, str], None]
PhaseCallback = Callable[[str], None]


def download_update(release: ReleaseInfo, progress_callback: ProgressCallback | None = None, phase_callback: PhaseCallback | None = None) -> Path:
    if not release.installer_url:
        raise RuntimeError("automatic_update_unsupported")
    if progress_callback is None and phase_callback is None:
        return _download_installer(release.installer_url, release.installer_sha256 or "")
    return _download_installer(release.installer_url, release.installer_sha256 or "", progress_callback, phase_callback)


def download_linux_update(release: ReleaseInfo, progress_callback: ProgressCallback | None = None, phase_callback: PhaseCallback | None = None) -> Path:
    if not release.linux_package_url:
        raise RuntimeError("linux_update_unavailable")
    downloads_directory = Path.home() / "Downloads"
    destination_directory = downloads_directory if downloads_directory.is_dir() else None
    if progress_callback is None and phase_callback is None:
        return _download_package(release.linux_package_url, release.linux_package_sha256 or "", destination_directory)
    return _download_package(release.linux_package_url, release.linux_package_sha256 or "", destination_directory, progress_callback, phase_callback)


def launch_update(installer_path: Path, parent_pid: int, application_path: str, log_path: Path) -> None:
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        raise RuntimeError("automatic_update_unsupported")
    subprocess.Popen(
        [sys.executable, "--apply-update", str(installer_path), str(parent_pid), application_path, str(log_path)],
        close_fds=True,
    )


def apply_update(installer_path: str, parent_pid: int, application_path: str, log_path: str) -> int:
    log = Path(log_path)
    if sys.platform != "win32" or not Path(installer_path).is_file():
        write_update_log(log, "Updater stopped: unsupported platform or installer is missing.")
        return 1
    write_update_log(log, f"Updater started for installer: {installer_path}")
    _wait_for_process(parent_pid)
    write_update_log(log, "Application closed. Starting visible installer.")
    try:
        installer = subprocess.Popen([installer_path, "/CLOSEAPPLICATIONS", "/NORESTART"], close_fds=True)
    except OSError as error:
        write_update_log(log, f"Could not start installer: {error}")
        return 1
    exit_code = installer.wait()
    write_update_log(log, f"Installer finished with exit code {exit_code}.")
    if exit_code != 0:
        return 1
    write_update_log(log, "Starting updated application.")
    subprocess.Popen([application_path], close_fds=True)
    return 0


def _download_installer(url: str, expected_sha256: str, progress_callback: ProgressCallback | None = None, phase_callback: PhaseCallback | None = None) -> Path:
    return _download_asset(url, expected_sha256, progress_callback=progress_callback, phase_callback=phase_callback)


def _download_package(url: str, expected_sha256: str, destination_directory: Path | None = None, progress_callback: ProgressCallback | None = None, phase_callback: PhaseCallback | None = None) -> Path:
    return _download_asset(url, expected_sha256, destination_directory, progress_callback, phase_callback)


def _download_asset(url: str, expected_sha256: str, destination_directory: Path | None = None, progress_callback: ProgressCallback | None = None, phase_callback: PhaseCallback | None = None) -> Path:
    destination_directory = destination_directory or Path(tempfile.gettempdir()) / "serial-vision-update"
    destination_directory.mkdir(parents=True, exist_ok=True)
    filename = Path(url.split("?", 1)[0]).name or "SerialVision-Setup.exe"
    destination = destination_directory / filename
    request = urllib.request.Request(url, headers={"User-Agent": "Serial-Vision"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as target:
        content_length = response.headers.get("Content-Length") if getattr(response, "headers", None) else None
        total = int(content_length) if content_length and content_length.isdigit() else None
        downloaded = 0
        while chunk := response.read(1024 * 1024):
            target.write(chunk)
            digest.update(chunk)
            downloaded += len(chunk)
            if progress_callback:
                progress_callback(downloaded, total, url)
    if phase_callback:
        phase_callback("verifying")
    if expected_sha256 and digest.hexdigest().lower() != expected_sha256.lower():
        destination.unlink(missing_ok=True)
        raise RuntimeError("update_integrity_failed")
    return destination


def create_update_log(data_directory: Path) -> Path:
    directory = data_directory / "update-logs"
    directory.mkdir(parents=True, exist_ok=True)
    prune_update_logs(directory)
    path = directory / f"update-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.log"
    write_update_log(path, "Update session started.")
    return path


def prune_update_logs(directory: Path, retention_days: int = 5) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    for path in directory.glob("*.log"):
        try:
            if datetime.fromtimestamp(path.stat().st_mtime, UTC) < cutoff:
                path.unlink()
        except OSError:
            continue


def write_update_log(path: Path, message: str) -> None:
    timestamp = datetime.now(UTC).isoformat()
    try:
        with path.open("a", encoding="utf-8") as target:
            target.write(f"{timestamp} {message}\n")
    except OSError:
        pass


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
