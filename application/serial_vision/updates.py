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
    if installer_asset is None:
        return ReleaseInfo(version, str(payload.get("body", "")), None)
    digest = str(installer_asset.get("digest", ""))
    return ReleaseInfo(
        version,
        str(payload.get("body", "")),
        str(installer_asset["browser_download_url"]),
        digest.removeprefix("sha256:") if digest.startswith("sha256:") else None,
    )


def launch_update(release: ReleaseInfo, parent_pid: int) -> None:
    if sys.platform != "win32" or not release.installer_url or not getattr(sys, "frozen", False):
        raise RuntimeError("automatic_update_unsupported")
    arguments = ["--apply-update", release.installer_url, release.installer_sha256 or "", str(parent_pid), sys.executable]
    subprocess.Popen([sys.executable, *arguments], close_fds=True)


def apply_update(installer_url: str, expected_sha256: str, parent_pid: int, application_path: str) -> int:
    if sys.platform != "win32":
        return 1
    destination = _download_installer(installer_url, expected_sha256)
    _wait_for_process(parent_pid)
    installer = subprocess.Popen([str(destination), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], close_fds=True)
    if installer.wait() != 0:
        return 1
    subprocess.Popen([application_path], close_fds=True)
    return 0


def _download_installer(url: str, expected_sha256: str) -> Path:
    destination_directory = Path(tempfile.gettempdir()) / "serial-vision-update"
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
