from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from serial_vision.application_service import SerialVisionService
from serial_vision.database import Database
from serial_vision.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Serial Vision")
    app.setOrganizationName("Serial Vision")
    app.setQuitOnLastWindowClosed(False)
    stylesheet = Path(__file__).with_name("assets").joinpath("app.qss").read_text(encoding="utf-8")
    app.setStyleSheet(stylesheet)
    data_directory = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    window = MainWindow(SerialVisionService(Database(data_directory / "serial-vision.sqlite3")))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
