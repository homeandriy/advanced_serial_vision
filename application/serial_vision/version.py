from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys


def app_version() -> str:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    candidates = (
        bundle_root / "VERSION",
        Path(sys.executable).resolve().parent / "VERSION",
        Path(__file__).resolve().parents[2] / "VERSION",
    )
    for candidate in candidates:
        try:
            value = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value
    try:
        return version("serial-vision")
    except PackageNotFoundError:
        return "0.0.0"
