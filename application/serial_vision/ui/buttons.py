from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QStyle, QWidget


BUTTONS: dict[str, QStyle.StandardPixmap] = {
    "save": QStyle.StandardPixmap.SP_DialogSaveButton,
    "delete": QStyle.StandardPixmap.SP_TrashIcon,
    "edit": QStyle.StandardPixmap.SP_FileDialogDetailedView,
    "refresh": QStyle.StandardPixmap.SP_BrowserReload,
    "folder": QStyle.StandardPixmap.SP_DirOpenIcon,
    "export": QStyle.StandardPixmap.SP_DialogSaveButton,
    "rotate": QStyle.StandardPixmap.SP_BrowserReload,
    "ocr": QStyle.StandardPixmap.SP_FileDialogContentsView,
}


def button(parent: QWidget, action: str, caption: str, tooltip: str | None = None) -> QPushButton:
    icon = BUTTONS[action]
    control = QPushButton(parent.style().standardIcon(icon), caption, parent)
    control.setToolTip(tooltip or caption)
    control.setAccessibleName(caption)
    return control
