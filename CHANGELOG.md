# Changelog

## [Unreleased]

## v0.7.5 - 2026-10-26

### Changed

- Enforce UTF-8 without BOM and LF through Git/editor settings, a staged-content pre-commit hook and CI.
- Split the main window into seven independent screens and an update controller; background gallery indexing, bounded thumbnail caching, statistics and camera decoding keep the interface responsive.
- Aggregate statistics in SQLite while preserving Kyiv time-zone boundaries and full equipment exports.
- Check the entire application with Mypy and generate the standalone updater translations from the shared three-language catalog in Make and CI.
- Update architecture and technical-debt documentation with reproducible before/after measurements for 5000 photos and 100 000 records.

### Fixed

- Normalize catalog roots before ownership checks, including Windows short paths and folders containing parent-directory segments.
- Save settings atomically and restore the previous local API configuration after a failed write, commit or port change; retain unsaved form changes on failure.
- Reject stale background gallery/statistics responses when the operator changes a folder or grouping.

## v0.7.4 - 2026-10-26

### Fixed

- Type checks follow the active Python interpreter, so Python 3.13 CI can read the newer NumPy type stubs. Python 3.11 remains covered by its own CI jobs.

## v0.7.3 - 2026-10-26

### Added

- The standalone Windows updater supports Ukrainian, English and Polish, automatic system-language detection, and switching language without interrupting download progress or losing the process log.
- Pull-request and main-branch CI checks for Linux and Windows, with Ruff lint/format validation, initial core type checks and regression tests.
- A prioritized technical-debt register with completion criteria and a record of resolved issues.

### Changed

- Development, tests and release packaging use uv with a shared dependency lockfile and Makefile commands.
- Recognition, image-editing, API authentication and startup-log retry messages are localized; equipment filters expose associated accessible labels.

### Fixed

- Exit now stops camera/API activity and waits for background workers before terminating the application.
- AI responses from a previous photo cannot replace the result of the selected photo.
- Unreadable photographs no longer leave recognition controls blocked.
- Equipment writes reject invalid data, updates to missing records return 404, and omitted photo references are preserved during updates.
- Date filters include fractional seconds at the end of the selected day, including daylight-saving transition days.
- Python packages include the standalone camera/scan icons and exclude the test package.

### Security

- Built-in Windows and Linux update downloads require a valid SHA-256 digest before fetching a package; checksum mismatches reject the downloaded file and prevent installation.
- Local API request bodies must be JSON objects within the configured size limit.

## v0.7.2 - 2026-10-14

### Added

- A non-destructive photo editor with adjustable crop handles, rotation, resizing, and image-adjustment sliders; its working copy can be recognized by OCR, barcode, and an explicitly selected AI profile.
- Optional right-angle rotation and image-enhancement recognition strategies, selectable in Settings, to recover labels in differently oriented or soft photos while retaining the original-image result as the first choice.
- Periodic update checks while the application stays open, with the release changelog shown before any download or installation.

### Changed

- Photo preview supports wheel zoom, Fit and 100% controls, adaptive gallery columns, and splitters whose positions are remembered.
- Recognition uses a single Retry action with stage and cancellation feedback; equipment filters and row actions are clearer, and Settings has one Save action with an unsaved-changes indicator.
- Choosing Later suppresses repeated automatic prompts for the same release during the current session; manual checks remain available.

### Fixed

- Refreshing or paging the gallery no longer leaves an invisible selected photo that could be processed or deleted accidentally.
- Recognition can fall back to serial and MAC-like values printed beside unreadable barcodes.
- The Linux release runner installs the system Qt and multimedia libraries required by headless UI tests before packaging.

## v0.6.2 - 2026-10-07

### Changed

- The verified Windows installer is now started directly before the application exits, so no second `SerialVision.exe` process holds the installed executable open during file replacement.
- The update log is permanently visible below the determinate progress bar and is refreshed through download verification and installer launch. Inno Setup writes its own installation log to the same file.

### Fixed

- Windows automatic installation no longer relies on the self-hosted updater helper that prevented the installer from replacing the running executable.

## v0.6.1 - 2026-10-06

### Changed

- The Windows update flow now shows the download URL, three explicit stages, true download progress, and an optional update log instead of an indefinite busy indicator.
- The verified Windows installer opens visibly after the application closes, rather than installing silently in the background.

### Fixed

- Update logs older than five days are removed automatically.
- The photo-catalog and preview panes can be fully resized with their vertical splitter.
- The About window is wider, has a cleaner status-bar presentation, and links to the Webbooks portfolio with UTM parameters.

## v0.6.0 - 2026-10-06

### Added

- Update dialog shows the published release changelog and lets the operator install now or defer the update without downloading anything.
- Ubuntu and other supported Linux desktops can download a SHA-256-verified DEB package and open it in the system package installer.
- Barcode recognition tries enlarged grayscale and contrast-enhanced image variants; serial and MAC-like values found in a barcode label by OCR are shown as a fallback.

### Changed

- OCR, barcode and AI result fields use a larger 16 px font for improved readability.

### Fixed

- The unavailable barcode-recognition-module message is localized in Ukrainian, English and Polish.

## v0.5.6 - 2026-08-28

### Changed

- Update checks now only notify the operator; installation requires explicit confirmation in Help → Check for updates.
- The application remains open while an approved Windows update is downloaded and SHA-256-verified.

### Fixed

- A per-user application lock prevents a second Serial Vision instance from running during normal use or an update.
- An update can no longer silently close the application immediately after an update check.


## v0.5.5 - 2026-08-28

### Added

- Ukrainian, English, and Polish end-user licence agreements for the EXE and MSI installers, portable Windows application, Debian package, and source archive.
- Dedicated eye and eye-off icons for the Scan tab and camera controls in every bundled icon style.

### Changed

- The Scan tab now appears immediately before API integrations; the camera has an explicit stop control and automatically stops when leaving the tab.

### Fixed

- Windows MSI builds receive the language-specific licence file instead of the WiX placeholder agreement.

## v0.5.4 - 2026-08-28

### Added

- Local camera Scan tab: operator-controlled video preview, still-frame capture, and offline QR/1D/2D barcode recognition.
- Copy-record action in the equipment edit form and safe API request examples for the edited record.
- `GET /api/v1/equipment/{id}` with an OpenAPI description.

### Changed

- Automatic update checks and release documentation now use the Advanced Serial Vision GitHub repository.
- GitHub Release notes include only the current version changelog section and commits since the preceding tag.

### Fixed

- Single-record model and equipment API reads now return 404 when the requested id does not exist.

## v0.5.3 - 2026-08-28

### Fixed

- Windows release workflow compiles the WiX file from the actual generated installer directory.

## v0.5.2 - 2026-08-28

### Fixed

- Windows release workflow no longer requests a missing Ukrainian WiX UI resource, so it can build all delivery packages.

## v0.5.1 - 2026-08-28

### Fixed

- Інсталятори Advanced Serial Vision встановлюються у власний каталог і не перезаписують попередній застосунок.
- PyInstaller-бандл містить VERSION, тому встановлений EXE коректно показує версію та не завершується з FileNotFoundError.
- MSI отримав майстер встановлення та окремі український, англійський і польський пакети.

### Changed

- Видима назва застосунку, інсталяторів, Swagger і довідки — Advanced Serial Vision.
- Дані поточного користувача ізольовані у каталозі homeandriy\Advanced Serial Vision.


## v0.5.0 - 2026-08-27

### Added

- Генерування QR-кодів і штрихкодів Code 128 для серійних номерів/MAC у формі та рядках обладнання.
- Авторизований API `POST /api/v1/code/get`, що віддає QR або Code 128 PNG-потоком для запису обладнання.
- Пакетні залежності для локального створення QR-кодів і штрихкодів.

### Changed

- Перегляд коду показує текстове значення; для штрихкоду також вказується технологія Code 128.
- Збережені та API-згенеровані коди отримують безпечні, однакові імена з типом, очищеним кодом і часом генерації.
- Дії запису обладнання відображаються компактними іконками з доступними підказками.


## v0.4.1 - 2026-08-26

### Added

- Імпорт довідника моделей з Excel `.xlsx` з перевіркою колонок, типів, послуг, дублікатів і некоректних рядків.
- Оновлений README з описом поточних функцій, локального API та встановлення.

## v0.4.0 - 2026-08-26

### Added

- Локальні API-інтеграції для BAS: Bearer-ключі, відкликання, строк дії, індивідуальні ліміти запитів та журнал операцій.
- OpenAPI/Swagger-документація для моделей, обладнання й захищеного отримання вихідних фото.
- Багатомовна довідка, світла і темна теми та локальні набори стилів іконок.

### Changed

- API обладнання не розкриває локальні шляхи: повертає лише назву фото; оригінал доступний окремим авторизованим потоком.
- Релізний workflow публікує точну версію з `VERSION` лише після push анотованого тегу.

### Fixed

- Уточнено запуск OCR, AI-розпізнавання та відкривання зображень у системному переглядачі.

## v0.3.0 - 2026-08-26

### Added
- Автоматичне оновлення Windows: перевірка GitHub Release через хвилину після запуску або вручну, завантаження інсталятора, SHA-256 перевірка та повторний запуск оновленого застосунку.
- Версіоновані транзакційні SQLite-міграції, що застосовуються під час старту без видалення локальних даних.

### Changed
- Вибране фото можна відкрити стандартним переглядачем операційної системи.

## v0.2.0 - 2026-08-26

### Added
- Автоматичне фонове OCR-розпізнавання та зчитування штрихкодів після вибору фото.
- Картки-перегляди зображень, згруповані за датою, і повне меню File/Edit/View/Help.
- Окремі блоки збереження налаштувань інтерфейсу, папки, оновлень та AI-профілів.

### Changed
- Інсталятори EXE, MSI і Debian пакують повну one-directory збірку PySide6/RapidOCR.

## v0.1.0 - 2026-08-26

### Added

- Added the local-first Python and Qt 6 foundation for Serial Vision.
- Added local SQLite storage, image-folder browsing, image rotation, RapidOCR OCR,
  equipment and model records, CSV export, and monthly operation statistics.
- Added project-level architecture, UI, testing, and release conventions.
