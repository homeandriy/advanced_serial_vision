from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

from PySide6.QtCore import QLockFile, QStandardPaths
from PySide6.QtWidgets import QApplication, QMessageBox

from serial_vision.application_service import SerialVisionService
from serial_vision.database import Database
from serial_vision.i18n import t
from serial_vision.ui.buttons import apply_button_icons
from serial_vision.ui.main_window import MainWindow
from serial_vision.ui.theme import apply_theme


def instance_lock_name() -> str:
    if os.name != "nt":
        return "serial-vision.lock"
    session_id = ctypes.c_ulong()
    if not ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session_id)):
        raise OSError("Cannot identify the Windows session")
    return f"serial-vision-session-{session_id.value}.lock"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Advanced Serial Vision")
    app.setOrganizationName("homeandriy")
    app.setQuitOnLastWindowClosed(False)
    data_directory = Path(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    )
    service = SerialVisionService(Database(data_directory / "serial-vision.sqlite3"))
    instance_lock = QLockFile(str(data_directory / instance_lock_name()))
    instance_lock.setStaleLockTime(0)
    if not instance_lock.tryLock(0):
        QMessageBox.information(
            None,
            t(service.locale(), "app_name"),
            t(service.locale(), "application_already_running"),
        )
        return 0
    try:
        apply_button_icons(service.icon_style())
        apply_theme(app, service.theme())
        window = MainWindow(service)
        window.show()
        return app.exec()
    finally:
        instance_lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
