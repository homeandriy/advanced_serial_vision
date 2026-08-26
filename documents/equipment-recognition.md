# OCR recognition and equipment registration

## Actor and objective

A local operator processes equipment-label photographs and records the recognized
serial numbers or MAC addresses. The application has no network account or role
model in v0.1.0; the Windows user who launches it is the operator.

## Inputs

- A selected local image folder and an image inside it.
- A local Tesseract executable and optional manually corrected OCR text.
- A model, operation (`receipt` or `issue`), optional contract number, and date/time.

## Flow and state changes

1. The operator selects a photo and runs OCR. The source photo remains unchanged.
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
- CSV export uses only the currently filtered records and Windows-1251 encoding for
  Microsoft Excel compatibility.

## Audit and future events

v0.1.0 has no user identity or audit table. Future record creation, update and
deletion must emit local audit events with timestamp, record ID, action and actor
identity when authentication is introduced.

## UI outcome

The operator sees the selected photo and editable OCR text, receives clear errors
when Tesseract or a directory is unavailable, and can subsequently find the record
through the equipment filters and statistics screen.
