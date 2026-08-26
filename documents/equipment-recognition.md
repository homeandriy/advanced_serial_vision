# OCR recognition and equipment registration

## Actor and objective

A local operator processes equipment-label photographs and records the recognized
serial numbers or MAC addresses. The application has no network account or role
model in v0.1.0; the Windows user who launches it is the operator.

## Inputs

- A selected local image folder and an image inside it.
- A local RapidOCR engine and optional manually corrected OCR text.
- On first run, explicit license acceptance and a selected image folder.
- A model, operation (`receipt` or `issue`), optional contract number, and date/time.

## Flow and state changes

1. The operator selects a photo from its dated preview card. OCR and barcode recognition start automatically; their result fields stay locked until the processing finishes. The source photo remains unchanged.
2. OCR creates temporary processed variants only; they are removed when recognition
   completes.
3. The operator can generate a QR code or a Code 128 barcode from the current serial/MAC/text field before saving, or from the compact QR/barcode actions of an existing equipment row. Preview titles identify the code value; barcode titles also identify the Code 128 technology. The preview may be saved as a PNG named `qrcode_<sanitized-code>_<H_M_d_m_Y>.png` or `barcode_<sanitized-code>_<H_M_d_m_Y>.png`; generating or saving a code never changes the equipment record.
4. The operator corrects text, selects a model and saves a new equipment record.
5. The SQLite transaction stores the immutable source-photo path reference and the
   operation data. The UI refreshes the equipment list and statistics.
6. AI recognition runs only when the operator explicitly presses the AI-recognition
   button after selecting both a photo and an AI profile. The prepared image is sent
   to the chosen provider; its API key is retrieved only from the operating-system
   credential store and is never persisted in SQLite.
7. The operator may choose a system, light or dark theme and one button/tab icon
   style: system, modern, classic, Windows 98, or Ubuntu 22. The non-system styles are bundled local SVG sets under `assets/icons/` and apply to buttons and tabs. System theme follows
   the OS at application startup; explicit operator choice is retained locally.
8. The operator creates, edits, or deletes equipment models, including their type and
   service. The models table shows each model usage count and supports sorting by
   name and numeric usage count. A model still cannot be deleted while equipment
   records reference it. The operator can import models from an XLSX worksheet named Models or Моделі with name, device_type and service columns. Only modem/tuner and internet/television are accepted; malformed rows are skipped and duplicate combinations remain unchanged.

## Validation and guards

- Image paths must resolve inside the selected image folder.
- A record requires non-empty recognized text and a known model.
- QR and Code 128 generation require non-empty text. The generated preview uses only the value currently entered by the operator; it is not persisted unless the operator explicitly saves its PNG.
- Model type and service are stable codes. A model is unique by name, type and service.
- A missing source photo is not a reason to delete its related equipment record.
- Deleting a photo, equipment record or model requires a confirmation. A model with
  related equipment records is protected by the database foreign-key constraint.
- CSV export uses every currently filtered record, including all paginated pages, and Windows-1251 encoding for Microsoft Excel compatibility.
- Contract number is limited to 20 characters. Equipment timestamps are stored in UTC and interpreted in Europe/Kyiv for input, filters and display.
- The image catalog is recursive but accepts only supported image files that still resolve inside the selected root folder.

## Audit and future events

v0.1.0 has no user identity or audit table. Future record creation, update and
deletion must emit local audit events with timestamp, record ID, action and actor
identity when authentication is introduced.

## UI outcome

The image area shows paged preview cards grouped by photo date. The operator sees
the selected photo and editable OCR text, receives clear errors when OCR or a
directory is unavailable, and can subsequently find the record through the
equipment filters and statistics screen. The application menu provides File,
Edit, View and Help actions. Settings are grouped into independently saved
interface, appearance, image-folder and AI-profile blocks. The update source is not displayed or editable.

## Local diagnostics and updates

Startup attempts to write timestamped records to `startup.log` in per-user app data. If the OS denies access, startup continues without writing the log, retries once after the window appears, and shows the operator a modal message with the exact log folder and OS error. The Help menu can open that file when available. The fixed official GitHub repository is checked in a worker thread one minute after startup and on demand. On Windows, a newer signed GitHub release EXE is downloaded to a temporary folder, verified against its SHA-256 release digest, then launched silently after the application closes; once setup succeeds, the helper relaunches the updated executable. The installer uses the stable AppId and does not touch per-user SQLite data. On the next start, forward-only SQLite migrations are applied transactionally using PRAGMA user_version; migrations never delete or recreate the database. On Linux, the operator receives a manual-installation notice because a DEB update can require system privileges.

## Scalability and statistics

The photo catalog is paged at 48 files. Equipment becomes paged at 100 rows only after 5,000 filtered rows, while export remains complete. Statistics aggregate receipt and issue operations, services and models in Europe/Kyiv and offer daily and monthly views.


## Local BAS API integration

### Actors, access and state

A BAS integration running on the same workstation can call the optional REST API at
`http://127.0.0.1:<port>/api/v1`. It is disabled by default and never binds to a
network interface. The operator enables it in Settings → API integrations and selects a port (default
`4556`). The separate API integrations tab is disabled until this setting is on.
Each issued key receives its own request interval: 200 ms (5/s), 500 ms (default,
2/s), 1 s, or 2 s. Changing API enablement or port restarts the local server.

The operator creates a Bearer key with a required name, optional note and optional
expiry timestamp. The raw key is shown once in a copyable dialog; only its SHA-256
hash and non-secret prefix are stored. A key cannot be viewed again; replacement
means issuing another key. The operator can revoke a key at any time. Expired or
revoked keys cannot authorize requests.

### API contract and validation

Every endpoint except `GET /api/v1/health` requires `Authorization: Bearer <key>`.
The rate limit is enforced per active key. `GET /models`, `POST /models`,
`PATCH /models/{id}`, `DELETE /models/{id}` and matching `/equipment` endpoints
use the same validation and database rules as the desktop UI. Model deletion is
protected while equipment uses it. Equipment write payloads use stable codes
`receipt`/`issue`, `modem`/`tuner`, `internet`/`television` and ISO 8601 timestamps.
OpenAPI is available at `/api/v1/openapi.json`; `/api/v1/docs` contains BAS/1C
request examples.

Equipment responses do not disclose the local `source_image_path`; they expose
only `source_image_name`, the file name with its extension. An authorized
integration first calls `GET /api/v1/image/check/{record_id}` to learn whether
the source file is still present and to receive its name. `record_id` is the
`id` of an equipment record, never the `device_model_id`. It may then call
`POST /api/v1/image/get` with `{ "record_id": <record_id> }`. When the file is
available, the API responds with its original image bytes, `Content-Type`, and
an RFC-compatible `Content-Disposition` attachment filename. BAS can save or
stream that response without receiving a workstation path. A missing record
returns 404; a missing, unreadable, or non-file source image returns 409. Both
routes require the same Bearer key, per-key rate limit, and audit entry as the
equipment routes.

An integration can generate a machine-readable code for an existing equipment
record without accessing its source photo: `POST /api/v1/code/get` with
`{ "record_id": <record_id>, "type": "qrcode" }` or
`{ "record_id": <record_id>, "type": "barcode" }`. Here `record_id` is the
equipment record `id`, never `device_model_id`. The API creates the PNG from that
record's `recognized_text` and returns its bytes with `Content-Type: image/png`
and an attachment `Content-Disposition` filename matching the desktop naming
rule. `barcode` uses Code 128. The generated code is not stored in the database.

### Audit and expected UI

Each HTTP request records its timestamp, authenticated key (when known), method,
path, status code and local client address in the local audit log. The API
integration UI lists keys without exposing secrets and supports issuing, copying
the newly issued secret, revoking keys and viewing recent API operations.
