from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


def resolved_theme(theme: str, app: QApplication) -> str:
    if theme != "system":
        return theme
    return "dark" if app.styleHints().colorScheme() == Qt.ColorScheme.Dark else "light"


def apply_theme(app: QApplication, theme: str) -> None:
    assets = Path(__file__).parents[1] / "assets"
    common = (assets / "app.qss").read_text(encoding="utf-8")
    selected = (assets / f"{resolved_theme(theme, app)}.qss").read_text(encoding="utf-8")
    app.setStyleSheet(f"{common}\n{selected}")
