# Tools

This directory is reserved for one-off, explicitly invoked maintenance tools.

The planned `migrate_legacy.py` tool will import a user-selected Laravel SQLite
database only after its schema is confirmed. It intentionally does not run as part
of application startup, so the Python application never modifies legacy data.
