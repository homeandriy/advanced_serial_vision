from __future__ import annotations

import sys
from pathlib import Path

from serial_vision.updates import apply_update

from PySide6.QtCore import QLockFile, QStandardPaths
from PySide6.QtWidgets import QApplication, QMessageBox

from serial_vision.application_service import SerialVisionService
from serial_vision.database import Database
from serial_vision.ui.buttons import apply_button_icons
from serial_vision.ui.main_window import MainWindow
from serial_vision.ui.theme import apply_theme
from serial_vision.i18n import t


def main() -> int:
    if "--apply-update" in sys.argv:
        index = sys.argv.index("--apply-update")
        try:
            installer_path, parent_pid, application_path = sys.argv[index + 1:index + 4]
        except ValueError:
            return 1
        return apply_update(installer_path, int(parent_pid), application_path)
    app = QApplication(sys.argv)
    app.setApplicationName("Advanced Serial Vision")
    app.setOrganizationName("homeandriy")
    app.setQuitOnLastWindowClosed(False)
    data_directory = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    service = SerialVisionService(Database(data_directory / "serial-vision.sqlite3"))
    instance_lock = QLockFile(str(data_directory / "serial-vision.lock"))
    instance_lock.setStaleLockTime(0)
    if not instance_lock.tryLock(0):
        QMessageBox.information(None, t(service.locale(), "app_name"), t(service.locale(), "application_already_running"))
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
