# Changelog

## [Unreleased]

### Added

- Added automatic GitHub releases with Windows EXE/MSI and Linux source/DEB artifacts.

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

