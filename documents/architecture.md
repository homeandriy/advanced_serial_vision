# Architecture

`serial_vision` is a local-first PySide6 desktop application.

- `Database` owns the SQLite schema and all persistence queries.
- `ImageCatalog` enumerates an explicitly selected image folder and guards every
  path against escaping it.
- `TesseractRecognizer` prepares three orientation variants and runs a local
  Tesseract process without requiring a Python OCR binding.
- Qt widgets stay in `ui/`; they call services through the main window rather than
  embedding persistence or OCR code in individual controls.

The database contains `device_models`, `devices`, and `settings`. Dates are saved
as UTC ISO-8601 values. The UI displays local time.

