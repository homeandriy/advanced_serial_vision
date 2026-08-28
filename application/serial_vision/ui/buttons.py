from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QPushButton, QStyle, QToolButton, QWidget


BUTTONS: dict[str, QStyle.StandardPixmap] = {
    "close": QStyle.StandardPixmap.SP_DialogCloseButton,
    "copy": QStyle.StandardPixmap.SP_FileDialogDetailedView,
    "save": QStyle.StandardPixmap.SP_DialogSaveButton,
    "delete": QStyle.StandardPixmap.SP_TrashIcon,
    "edit": QStyle.StandardPixmap.SP_FileDialogDetailedView,
    "refresh": QStyle.StandardPixmap.SP_BrowserReload,
    "folder": QStyle.StandardPixmap.SP_DirOpenIcon,
    "open_image": QStyle.StandardPixmap.SP_FileIcon,
    "export": QStyle.StandardPixmap.SP_DialogSaveButton,
    "rotate": QStyle.StandardPixmap.SP_BrowserReload,
    "previous": QStyle.StandardPixmap.SP_ArrowBack,
    "next": QStyle.StandardPixmap.SP_ArrowForward,
    "ocr": QStyle.StandardPixmap.SP_FileDialogContentsView,
    "open": QStyle.StandardPixmap.SP_DialogOpenButton,
    "recognition": QStyle.StandardPixmap.SP_FileDialogContentsView,
    "equipment": QStyle.StandardPixmap.SP_DriveHDIcon,
    "models": QStyle.StandardPixmap.SP_FileDialogDetailedView,
    "statistics": QStyle.StandardPixmap.SP_FileDialogInfoView,
    "settings": QStyle.StandardPixmap.SP_FileDialogListView,
    "api_integrations": QStyle.StandardPixmap.SP_DialogHelpButton,
    "generate_qr": QStyle.StandardPixmap.SP_FileDialogContentsView,
    "generate_barcode": QStyle.StandardPixmap.SP_FileDialogDetailedView,
    "camera": QStyle.StandardPixmap.SP_ComputerIcon,
    "scan": QStyle.StandardPixmap.SP_ComputerIcon,
    "capture": QStyle.StandardPixmap.SP_DialogSaveButton,
    "stop": QStyle.StandardPixmap.SP_MediaStop,
    "api_example": QStyle.StandardPixmap.SP_DialogHelpButton,
    "copy_record": QStyle.StandardPixmap.SP_FileDialogNewFolder,
}


def button(parent: QWidget, action: str, caption: str, tooltip: str | None = None) -> QPushButton:
    control = QPushButton(caption, parent)
    control.setProperty("button_action", action)
    _set_icon(control, action)
    control.setToolTip(tooltip or caption)
    control.setAccessibleName(caption)
    return control


def compact_button(parent: QWidget, action: str, tooltip: str) -> QToolButton:
    control = QToolButton(parent)
    control.setAutoRaise(True)
    control.setProperty("button_action", action)
    control.setProperty("compact_action", True)
    control.setFixedSize(24, 24)
    _set_icon(control, action)
    control.setToolTip(tooltip)
    control.setAccessibleName(tooltip)
    return control


ICON_SIZES = {"system": 16, "modern": 20, "classic": 16, "windows98": 14, "ubuntu22": 18}


def icon_size(style: str) -> QSize:
    size = ICON_SIZES.get(style, 16)
    return QSize(size, size)


def apply_button_icons(style: str) -> None:
    app = QApplication.instance()
    if app is None:
        return
    app.setProperty("icon_style", style)
    for widget in app.allWidgets():
        if isinstance(widget, (QPushButton, QToolButton)):
            action = widget.property("button_action")
            if action:
                _set_icon(widget, str(action))


def icon_for(parent: QWidget, action: str) -> QIcon:
    app = QApplication.instance()
    style = str(app.property("icon_style")) if app is not None and app.property("icon_style") else "system"
    icon_root = Path(__file__).parents[1] / "assets" / "icons"
    asset = icon_root / style / f"{action}.svg"
    if style != "system" and asset.is_file():
        return QIcon(str(asset))
    if action in {"scan", "camera", "stop"}:
        return QIcon(str(icon_root / f"{action}.svg"))
    return parent.style().standardIcon(BUTTONS[action])


def _set_icon(control: QPushButton | QToolButton, action: str) -> None:
    app = QApplication.instance()
    style = str(app.property("icon_style")) if app is not None and app.property("icon_style") else "system"
    control.setProperty("icon_style", style)
    control.setIconSize(icon_size(style))
    control.setIcon(icon_for(control, action))
