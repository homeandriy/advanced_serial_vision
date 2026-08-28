# Changelog

## [Unreleased]

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

