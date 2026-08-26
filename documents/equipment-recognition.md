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
3. The operator corrects text, selects a model and saves a new equipment record.
4. The SQLite transaction stores the immutable source-photo path reference and the
   operation data. The UI refreshes the equipment list and statistics.
5. When an AI profile is selected, selecting an image submits the same prepared
   image to that user-configured provider; its API key is retrieved only from the
   operating-system credential store and is never persisted in SQLite.

## Validation and guards

- Image paths must resolve inside the selected image folder.
- A record requires non-empty recognized text and a known model.
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
interface, image-folder, update and AI-profile blocks.

## Local diagnostics and updates

Startup writes timestamped records to `startup.log` in per-user app data. The Help menu can open that file. A configured GitHub repository is checked in a worker thread one minute after startup and on demand. On Windows, a newer signed GitHub release EXE is downloaded to a temporary folder, verified against its SHA-256 release digest, then launched silently after the application closes; once setup succeeds, the helper relaunches the updated executable. The installer uses the stable AppId and does not touch per-user SQLite data. On the next start, forward-only SQLite migrations are applied transactionally using PRAGMA user_version; migrations never delete or recreate the database. On Linux, the operator receives a manual-installation notice because a DEB update can require system privileges.

## Scalability and statistics

The photo catalog is paged at 48 files. Equipment becomes paged at 100 rows only after 5,000 filtered rows, while export remains complete. Statistics aggregate receipt and issue operations, services and models in Europe/Kyiv and offer daily and monthly views.
