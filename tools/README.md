# Tools

This directory is reserved for one-off, explicitly invoked maintenance tools.

`advance_serial_vision_path_updater.py` is a standalone Windows/Tk updater for
older installations. Run it explicitly with Python; it needs no installed
Serial Vision or PySide6 package. It detects the Windows UI language and offers
Automatic, Ukrainian, English and Polish choices. The selection is kept for the
current session; changing it also translates the current status and existing log.
Downloads and installer launch still require pressing the installation button.
Its embedded `UPDATER_TEXT` mirrors the `updater_*` entries in
`serial_vision.i18n.TEXT`; update both catalogs together. Tests check they match.

The planned `migrate_legacy.py` tool will import a user-selected Laravel SQLite
database only after its schema is confirmed. It intentionally does not run as part
of application startup, so the Python application never modifies legacy data.
