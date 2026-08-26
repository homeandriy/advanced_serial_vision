from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    changelog: str
    installer_url: str | None


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
    installer = next(
        (str(asset["browser_download_url"]) for asset in payload.get("assets", []) if str(asset.get("name", "")).lower().endswith(".exe")),
        None,
    )
    return ReleaseInfo(version, str(payload.get("body", "")), installer)


def _is_newer(candidate: str, current: str) -> bool:
    def normalize(value: str) -> tuple[int, ...]:
        return tuple(int(part) for part in re.findall(r"\d+", value)[:3])

    return normalize(candidate) > normalize(current)
