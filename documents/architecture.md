# Architecture

Serial Vision is a local-first Python 3.11+ desktop application using PySide6,
SQLite, Pillow, RapidOCR and ZXing. The central product scenario and safety
guards are in [equipment-recognition.md](equipment-recognition.md).

## Boundaries and ownership

- `main.py` creates the per-user Qt app-data directory, SQLite database and
  single-instance lock. Runtime data never belongs in the installation folder.
- `ui/main_window.py` owns navigation, cross-screen signal connections, first-run
  setup, application menus and shutdown. Independent QWidget screens in
  `ui/pages/` own recognition, equipment, models, statistics, camera, API and
  settings. Screens use application services; they contain no SQL or direct OCR.
- `ui/pages/base.py` provides shared presentation helpers and signals requesting
  help or equipment registration. Screens do not reach through the main window
  into another screen. Equipment receives a callback for the selected source photo.
- `SerialVisionService` validates operations and coordinates persistence,
  recognition options, credentials, imports, exports and settings. Typed result
  contracts live in `contracts.py`; immutable form input lives in `settings.py`.
- `Database` owns SQLite queries, connection lifetime and transactions.
  `ImageCatalog`, `ThumbnailCache`, recognition engines and code-image helpers
  own their focused infrastructure operations.
- `ui/update_controller.py` owns periodic/manual update checks and installation
  dialogs. It requests application shutdown through a signal.

Model changes refresh equipment choices and statistics through signals; equipment
changes refresh model usage counts and statistics. A successful settings save
updates appearance/folder/API availability through one main-window connection.

## Persistence

The current SQLite schema version is 4, with seven tables:

| Table | Responsibility |
| --- | --- |
| `settings` | User configuration, recognition options, splitter state |
| `device_models` | Stable equipment type/service codes and model names |
| `devices` | Operations, recognized text, contract, UTC timestamp and source-photo reference |
| `ai_agents` | Provider/model metadata and credential-store identifiers |
| `application_state` | Launch count and update time |
| `api_keys` | SHA-256 token hashes, expiry, revocation and rate interval |
| `api_audit` | Local API request outcomes |

Foreign keys protect referenced models. Dates are stored as UTC ISO-8601; views,
date filters and statistics use Europe/Kyiv, including DST. SQL statistics return
grouped rows only; a deterministic SQLite function converts UTC to Kyiv periods
before aggregation. Equipment lists paginate above 5000 rows; CSV export obtains
all matching rows independently of the visible page.

Settings validation precedes one batch transaction. API reconfiguration receives
the proposed enabled flag and port explicitly before commit. Failure rolls back
SQLite and restores the previous API configuration; a failed compensation is
reported separately. Appearance and folder changes apply only after success.
Changing the language takes effect after restarting the application.

## Background work and responsiveness

OCR/barcode, optional AI, updates, gallery loading and statistics use QThread
workers. Workers compute data; Qt widgets and QPixmap creation remain on the GUI
thread. Statistics queries open their own short-lived database connections.

Gallery indexing captures path, relative name, modification nanoseconds and size
once. Page changes reuse the snapshot; explicit Refresh, rotation and deletion
invalidate it. A single gallery worker processes the latest pending request,
checking cancellation between files. Pillow decodes/resizes thumbnails in that
worker. The LRU PNG cache is limited to 256 entries and 16 MiB, keyed by path,
mtime and size. The GUI decodes only the small PNG payloads.

Generation counters discard stale gallery, statistics, OCR and AI replies.
AI replies also match the selected photo and profile. Refresh preserves a
still-visible selection; a page change clears selection immediately. Closing
stops camera/API/timers, cancels pending requests and waits for running workers
before quitting. Cancellation is cooperative: an active third-party decoder or
SQL statement finishes before shutdown can complete.

Reproducible timings and memory limits are documented in
[scalability.md](scalability.md). Index and cache are in memory for this session;
they do not create a background file watcher. External file changes become
visible after Refresh.

## Offline operation, API and updates

Local OCR, camera decoding, equipment CRUD and exports work offline. AI runs
only after an explicit action and reads its key from the OS credential store.
SQLite contains credential identifiers rather than AI secrets.

The optional local HTTP API binds only to 127.0.0.1. Bearer authentication checks
token hashes, expiry, revocation and per-key rate limits. Public response
contracts remain described by the generated OpenAPI document.

Update checks are optional network operations. Windows EXE and Linux DEB
downloads require a valid SHA-256 from release metadata and verify the payload
before installation. Missing/invalid/mismatched checksums block installation.

All user-facing text is in `i18n.TEXT` with Ukrainian, English and Polish values.
The independent Tk updater embeds an automatically generated `updater_*` subset.
Run `make updater-translations` after edits; `make check-translations` and CI
detect stale generated text. It still runs without the installed application.

## Development and verification

`pyproject.toml`, `.python-version` and `uv.lock` define reproducible environments.
Use `make install`, `make run`, `make format` and `make verify`; override `UV`
when uv is not on PATH. No Docker/Compose runtime is defined for this desktop app.

`make verify` checks the lock, compiles application sources, runs Ruff lint and
format checks, verifies generated translations, checks the entire application
package with Mypy and runs unittest regression tests. CI runs the same checks
on Linux Python 3.11/3.13 and Windows Python 3.11. Mypy follows the active
interpreter, avoiding incompatible syntax targets for installed NumPy stubs.
