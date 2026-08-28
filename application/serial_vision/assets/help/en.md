<!-- section: overview -->
## About Advanced Serial Vision

Advanced Serial Vision is a local application for equipment records and photographs of factory labels. It helps an operator extract a serial number, MAC address, barcode or other text, check it, and save a structured equipment operation. Records and settings stay in the current user's local data folder; normal daily work does not require an Internet connection.

The usual workflow is: select a photograph, use local recognition, correct the value when necessary, select a model and save the record. Saved records can be found with filters, linked back to their source photo, exported to CSV and included in statistics.

<!-- section: first-start -->
## First start and local data

At first launch, accept the terms and select the root folder containing photographs. Advanced Serial Vision reads supported image files from that folder and its subfolders; it does not move them by itself. Choose a folder that the current Windows user can access.

The image folder is not the application installation folder. The local database, settings and startup log are stored in the user's application-data directory, so updates should not remove equipment records. If a source folder or file is moved later, its existing record stays in the database, but opening the linked photo may no longer work.

<!-- section: navigation -->
## Navigation and safe work

Use Recognition for one selected photo, Equipment for the saved register and exports, Models for the controlled model directory, Statistics for summaries, and Settings for language, appearance, folders and optional AI profiles. The File, View and Help menus provide the same key actions.

Question-mark buttons open the matching help topic. Tooltips explain compact icon buttons. Deleting a photo never deletes its equipment record. Deleting a model that is used by records is blocked to protect historical data. Always read the confirmation before accepting a delete action.

<!-- section: images -->
## Photographs: selection and preparation

The image catalogue is recursive and paged, so it can work with large folders. Select an image card to see a larger preview. Local OCR and barcode reading start in the background after selection; wait for the result and check it carefully.

Use Rotate right only for the intended source file, because it changes that image. Open opens it in the system viewer. Delete is limited to files inside the selected image root and asks for confirmation. For best results, photograph the label sharply, straight on, without glare, and leave a small margin around text or the barcode.

<!-- section: ocr -->
## Local OCR recognition

Advanced Serial Vision uses RapidOCR locally. Selecting or running OCR does not send the image to a cloud service. Choose the OCR language that best matches the label: English for most technical serial labels, Ukrainian or Polish for supporting text. The language improves recognition but does not replace human checking.

The OCR result is editable. Copy it from the context menu or Edit menu, then correct ambiguous characters before saving. Typical label mistakes are O/0, I/1, S/5 and B/8. If no text is found, try a clearer source photo, a different orientation or another OCR language.

<!-- section: barcode-ai -->
## Barcodes and optional AI recognition

Use Read barcodes to extract a supported 1D or 2D barcode from the selected photograph. A missing result can simply mean the code is too small, damaged, reflective or unsupported. Copy a result where it is needed; barcode output itself is read-only.

AI recognition is optional and never runs automatically. It requires a selected photo and an AI profile with a provider, model and API key. The secret is stored in the operating-system credential store rather than SQLite. An AI request can send a prepared image to the chosen provider, so use it only when that transfer is permitted by your privacy rules.

<!-- section: equipment -->
## Registering equipment

Open Equipment and choose Add record. Enter the operation date and time, optional contract number, operation type, checked serial number/MAC/text, model, device type and service. The primary text is required; a contract number is limited to twenty characters.

Receipt and Issue are the two operation directions. Current device types are Modem and Tuner; services are Internet and Television. Display labels follow the interface language, while stable codes are kept in the database. Times are entered and displayed in Europe/Kyiv and stored in UTC. A record stores a reference to the source photo, not a duplicate of the file.

Double-click a table row or use Edit to correct a record. Removing a record is irreversible for the local database. For important history, follow your organisation's rules and verify the number, date and model before confirming.

In the record form, the serial/MAC field has Get QR code and Get barcode buttons. They create a code only from the current text, open a preview, and can save a PNG. Creating a code does not save or modify the equipment record.

<!-- section: search-export -->
## Search, filters and CSV export

Equipment filters cover date range, model, operation, device type, service and a text fragment. Combine them, then press Refresh. For example, find all Internet modem issues for a month or a fragment of a serial number.

The table is paged for large result sets, but Export CSV exports every record that matches the active filters, not only the current page. Check all active controls before exporting. Use a clear filename and preserve the exported original before making spreadsheet edits. CSV uses Windows-1251 encoding for common Microsoft Excel compatibility in Ukrainian Windows environments.

<!-- section: models -->
## Model directory

Models is a controlled list of common equipment. Each model has a name, device type and service. Create it once and reuse it during registration to keep exports and statistics consistent. The same name, type and service combination cannot be duplicated.

The table can be sorted by name or usage count. The count is the number of related historical records, not stock on hand. A model linked to equipment records cannot be deleted; create a new model for a new variant instead.

<!-- section: statistics -->
## Statistics and charts

Statistics groups saved operations by day or month. The table separately shows Receipts, Issues and their total. Charts summarize operations, services and up to ten most frequently recorded models.

Chart values are counts of records, not a live inventory balance. To inspect a particular device, return to Equipment and search the detailed journal. If a summary looks incomplete, verify the saved dates, models, operation directions, types and services in the original records.

<!-- section: settings -->
## Interface and appearance settings

Choose Ukrainian, English or Polish in Interface settings, save it and restart the application to apply the language. Changing language affects labels only, not the underlying codes or saved records.

Change the image folder only deliberately. Appearance supports system, light and dark themes plus system, modern, classic, Windows 98 and Ubuntu 22 icon styles. These choices change presentation, not data. AI profiles are managed here; never share an API key in a screenshot, message or CSV file.

<!-- section: updates-diagnostics -->
## Updates, startup log and troubleshooting

Help contains Check for updates and Open startup log. The official repository is checked in the background about a minute after startup and on request. On Windows, an available installer is downloaded to a temporary folder, verified by SHA-256 and run after the application closes. The per-user database is not part of the installer.

Linux updates require manual installation because DEB installation may require system rights. Use only official GitHub Release assets. When reporting an issue, include the application version, reproduction steps and a safe log excerpt without API keys or personal data.

<!-- section: privacy -->
## Privacy, backups and daily checklist

RapidOCR, barcode recognition, equipment records and settings work locally by default. Network use occurs only for an explicitly requested AI recognition or update check. Confirm that a photograph may be sent outside the device before using AI.

Back up the application-data folder and keep original photographs in reliable storage. CSV is a useful report, not a complete backup. Daily routine: choose the correct folder; select a clear photo; check OCR or barcode result; choose the correct model and operation; save; find the record if needed; and check the active filters before export.


<!-- section: integrations -->
## Integrations

Enable the local API in Settings, create a Bearer key in API integrations, and copy it once. Use Authorization: Bearer sv_... in BAS or Postman. Example: GET http://127.0.0.1:4556/api/v1/equipment. Swagger: http://127.0.0.1:4556/api/v1/docs.

Equipment responses expose only `source_image_name`, never the local file path. Call `GET /api/v1/image/check/{record_id}` first. `record_id` is the `id` of an equipment record, not `device_model_id`. When it returns `available: true`, send `POST /api/v1/image/get` with `{ "record_id": 123 }`. The response streams the image bytes and provides the original filename with extension in the standard `Content-Disposition` HTTP header.

To obtain a code for an existing equipment record through the API, send `POST /api/v1/code/get` with JSON `{ "record_id": 123, "type": "qrcode" }` or `{ "record_id": 123, "type": "barcode" }`. `record_id` is the equipment record `id`, not `device_model_id`. The response is a PNG stream: `barcode` uses Code 128, and a name such as `qrcode_AABBCCDDEEFF_14_30_27_08_2026.png` or `barcode_AABBCCDDEEFF_14_30_27_08_2026.png` is sent in `Content-Disposition`. The code is generated from `recognized_text` and is not separately stored in the database.
