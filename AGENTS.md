# Serial Vision — project instructions

## Product and stack

Serial Vision is a local-first Windows desktop application for recognizing serial
numbers and MAC addresses in photographs and registering equipment operations.

- Python 3.11+, PySide6 / Qt 6, SQLite, Pillow, and local Tesseract OCR.
- Use the per-user app-data directory for database and user settings. Do not write
  to the installation directory at runtime.
- The application must work without a network connection. AI recognition is an
  optional future integration and must not block local OCR or equipment records.

## Architecture

Keep a modular, layered design: `ui` -> application services -> domain and
infrastructure. Qt widgets never construct SQL queries or run OCR processes
directly; they call application services. Keep persistence, image IO and external
processes behind focused service classes.

The central user scenario is documented in
[documents/equipment-recognition.md](documents/equipment-recognition.md). Update
it before changing OCR, equipment records, source-photo links, validation, or
export behavior.

## UI and accessibility

- Use responsive Qt layouts and model/view controls, not fixed geometry.
- Keep visual styling in `.qss` resources, never inline in Python.
- Every visible text button has a semantic standard Qt icon, Ukrainian caption and
  tooltip; compact icon-only controls also need accessible names.
- Design for Ukrainian first and keep stable codes (`receipt`, `issue`, `modem`,
  `tuner`, `internet`, `television`) separate from displayed labels.
- Every new user-facing string must be a key in `serial_vision.i18n.TEXT` with
  Ukrainian, English and Polish translations. Do not add literal UI text in Python.

## Data safety

- Never alter or delete the legacy Laravel database automatically.
- Keep the equipment source-image path only as a reference; deleting an image must
  require an explicit confirmation and never delete its equipment record.
- Do not run destructive commands, schema migrations against user data, or delete
  app-data without explicit user approval.

## Workflow and verification

- Make small, focused edits with `apply_patch`; inspect usages before changing a
  public behavior.
- Run `python -m compileall -q application` and focused tests through `.venv`.
- Keep `VERSION` as strict `MAJOR.MINOR.PATCH` and `CHANGELOG.md` in Keep a
  Changelog form. Do not commit, tag, or publish without explicit user direction.
