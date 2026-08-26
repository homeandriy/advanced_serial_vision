# Serial Vision

Python 3.11 + PySide6 rewrite of the NativePHP desktop utility for finding serial
numbers and MAC addresses on equipment photographs.

## Current scope

The desktop version provides local SQLite storage, image-folder scanning, RapidOCR
OCR, barcode recognition, image rotation, AI profiles for OpenAI/Anthropic/Gemini,
and a localized Windows packaging workflow. Provider keys are stored locally in
Windows Credential Manager, never in SQLite or source control.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m serial_vision.main
```

Or use `make install` and `make run` where GNU Make is available.

The application stores its SQLite database and preferences in the per-user app-data
directory. OCR uses the bundled local RapidOCR engine; no external executable is required.

## Project layout

- `application/` — application code and tests
- `documents/` — architecture and migration notes
- `tools/` — standalone migration and packaging helpers
- `scripts/` — local development commands
