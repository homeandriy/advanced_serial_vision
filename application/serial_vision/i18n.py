from __future__ import annotations

from serial_vision.warehouse.translations import WAREHOUSE_TEXT

SUPPORTED_LOCALES = ("uk", "en", "pl")


def system_locale() -> str:
    from PySide6.QtCore import QLocale

    candidate = QLocale.system().name().split("_", 1)[0].lower()
    return candidate if candidate in SUPPORTED_LOCALES else "uk"


def t(locale: str, key: str, **values: object) -> str:
    return TEXT[locale].get(key, TEXT["uk"][key]).format(**values)


def error_message(locale: str, error: BaseException | str) -> str:
    """Translate application error keys while preserving external error details."""
    key = str(error)
    return t(locale, key) if key in TEXT["uk"] else key


_uk = {
    "app_name": "Advanced Serial Vision",
    "open": "Відкрити",
    "exit": "Вийти",
    "recognition": "Розпізнавання",
    "equipment": "Обладнання",
    "models": "Моделі",
    "statistics": "Статистика",
    "settings": "Налаштування",
    "help": "Довідка",
    "about": "Про програму",
    "images": "Зображення",
    "ocr": "OCR-розпізнавання",
    "barcodes": "Штрихкоди",
    "ai": "AI-розпізнавання",
    "ocr_language": "Мова OCR",
    "select_image": "Оберіть фото",
    "ocr_empty": "Результат OCR з’явиться тут.",
    "barcode_empty": "Результат штрихкодів з’явиться тут.",
    "ai_empty": "Додайте та оберіть AI-профіль у налаштуваннях.",
    "refresh": "Оновити",
    "rotate": "Повернути праворуч",
    "delete": "Видалити",
    "run_ocr": "Розпізнати OCR",
    "run_barcode": "Прочитати штрихкоди",
    "choose_folder": "Обрати папку",
    "open_folder": "Відкрити папку",
    "save": "Зберегти",
    "export": "Експорт CSV",
    "language": "Мова інтерфейсу",
    "image_folder": "Папка з фото",
    "ai_profiles": "AI-профілі",
    "profile_name": "Назва",
    "provider": "Постачальник",
    "model": "Модель",
    "api_key": "API-ключ",
    "add_profile": "Додати профіль",
    "remove_profile": "Видалити профіль",
    "no_profiles": "AI-профілі ще не налаштовані.",
    "developer": "Розробник: homeandriy",
    "version": "Версія {version}",
    "type": "Тип",
    "service": "Послуга",
    "all_types": "Усі типи",
    "all_services": "Усі послуги",
    "modem": "Модем",
    "tuner": "Тюнер",
    "internet": "Інтернет",
    "television": "Телебачення",
    "receipt": "Прийом",
    "issue": "Видача",
    "operation": "Операція",
    "contract": "Номер договору",
    "recognized_text": "Серійний номер / MAC / текст",
    "date_time": "Дата і час",
    "model_name": "Назва моделі",
    "search": "Пошук за текстом",
    "confirm": "Підтвердження",
    "error": "Помилка",
    "no_image": "Спершу виберіть зображення.",
    "folder_missing": "Вибрана папка не існує або недоступна.",
    "profile_saved": "AI-профіль збережено.",
    "profile_required": "Оберіть AI-профіль.",
    "restart_language": "Мову збережено. Вона застосовується після перезапуску.",
    "status_ready": "Готово",
    "barcodes_not_found": "Штрихкодів не знайдено.",
    "about_text": "Локальний облік обладнання та OCR.",
    "delete_image": "Видалити вибране фото? Запис обладнання залишиться.",
    "delete_device": "Видалити вибраний запис обладнання?",
    "delete_model": "Видалити вибрану модель?",
}

_en = {
    "app_name": "Advanced Serial Vision",
    "recognition": "Recognition",
    "equipment": "Equipment",
    "models": "Models",
    "statistics": "Statistics",
    "settings": "Settings",
    "help": "Help",
    "about": "About",
    "images": "Images",
    "ocr": "OCR recognition",
    "barcodes": "Barcodes",
    "ai": "AI recognition",
    "ocr_language": "OCR language",
    "select_image": "Select an image",
    "ocr_empty": "OCR result will appear here.",
    "barcode_empty": "Barcode result will appear here.",
    "ai_empty": "Add and select an AI profile in Settings.",
    "refresh": "Refresh",
    "rotate": "Rotate right",
    "delete": "Delete",
    "run_ocr": "Run OCR",
    "run_barcode": "Read barcodes",
    "choose_folder": "Choose folder",
    "open_folder": "Open folder",
    "save": "Save",
    "export": "Export CSV",
    "language": "Interface language",
    "image_folder": "Image folder",
    "ai_profiles": "AI profiles",
    "profile_name": "Name",
    "provider": "Provider",
    "model": "Model",
    "api_key": "API key",
    "add_profile": "Add profile",
    "remove_profile": "Remove profile",
    "no_profiles": "No AI profiles configured.",
    "developer": "Developer: homeandriy",
    "version": "Version {version}",
    "type": "Type",
    "service": "Service",
    "all_types": "All types",
    "all_services": "All services",
    "modem": "Modem",
    "tuner": "Tuner",
    "internet": "Internet",
    "television": "Television",
    "receipt": "Receipt",
    "issue": "Issue",
    "operation": "Operation",
    "contract": "Contract number",
    "recognized_text": "Serial number / MAC / text",
    "date_time": "Date and time",
    "model_name": "Model name",
    "search": "Search text",
    "confirm": "Confirmation",
    "error": "Error",
    "no_image": "Select an image first.",
    "folder_missing": "The selected folder is unavailable.",
    "profile_saved": "AI profile saved.",
    "profile_required": "Select an AI profile.",
    "restart_language": "Language saved. It will apply after restart.",
    "status_ready": "Ready",
    "barcodes_not_found": "No barcodes found.",
    "about_text": "Local equipment records and OCR.",
    "delete_image": "Delete selected photo? Equipment records stay.",
    "delete_device": "Delete selected equipment record?",
    "delete_model": "Delete selected model?",
}

_pl = {
    "app_name": "Advanced Serial Vision",
    "recognition": "Rozpoznawanie",
    "equipment": "Sprzęt",
    "models": "Modele",
    "statistics": "Statystyki",
    "settings": "Ustawienia",
    "help": "Pomoc",
    "about": "O programie",
    "images": "Obrazy",
    "ocr": "Rozpoznawanie OCR",
    "barcodes": "Kody kreskowe",
    "ai": "Rozpoznawanie AI",
    "ocr_language": "Język OCR",
    "select_image": "Wybierz obraz",
    "ocr_empty": "Wynik OCR pojawi się tutaj.",
    "barcode_empty": "Wynik kodów pojawi się tutaj.",
    "ai_empty": "Dodaj i wybierz profil AI w Ustawieniach.",
    "refresh": "Odśwież",
    "rotate": "Obróć w prawo",
    "delete": "Usuń",
    "run_ocr": "Uruchom OCR",
    "run_barcode": "Odczytaj kody",
    "choose_folder": "Wybierz folder",
    "open_folder": "Otwórz folder",
    "save": "Zapisz",
    "export": "Eksport CSV",
    "language": "Język interfejsu",
    "image_folder": "Folder obrazów",
    "ai_profiles": "Profile AI",
    "profile_name": "Nazwa",
    "provider": "Dostawca",
    "model": "Model",
    "api_key": "Klucz API",
    "add_profile": "Dodaj profil",
    "remove_profile": "Usuń profil",
    "no_profiles": "Brak profili AI.",
    "developer": "Programista: homeandriy",
    "version": "Wersja {version}",
    "type": "Typ",
    "service": "Usługa",
    "all_types": "Wszystkie typy",
    "all_services": "Wszystkie usługi",
    "modem": "Modem",
    "tuner": "Tuner",
    "internet": "Internet",
    "television": "Telewizja",
    "receipt": "Przyjęcie",
    "issue": "Wydanie",
    "operation": "Operacja",
    "contract": "Numer umowy",
    "recognized_text": "Numer seryjny / MAC / tekst",
    "date_time": "Data i czas",
    "model_name": "Nazwa modelu",
    "search": "Szukaj tekstu",
    "confirm": "Potwierdzenie",
    "error": "Błąd",
    "no_image": "Najpierw wybierz obraz.",
    "folder_missing": "Wybrany folder jest niedostępny.",
    "profile_saved": "Profil AI zapisano.",
    "profile_required": "Wybierz profil AI.",
    "restart_language": "Język zapisano. Zostanie zastosowany po restarcie.",
    "status_ready": "Gotowe",
    "barcodes_not_found": "Nie znaleziono kodów kreskowych.",
    "about_text": "Lokalna ewidencja sprzętu i OCR.",
    "delete_image": "Usunąć wybrane zdjęcie? Rekordy sprzętu pozostaną.",
    "delete_device": "Usunąć wybrany rekord sprzętu?",
    "delete_model": "Usunąć wybrany model?",
}

_uk.update(
    {
        "shutdown_wait": "Завершення фонових операцій перед виходом…",
        "recognized_text_required": "Введіть серійний номер, MAC-адресу або текст.",
        "contract_invalid": "Номер договору має бути текстом.",
        "operation_invalid": "Оберіть операцію прийому або видачі.",
        "model_required": "Оберіть наявну модель обладнання.",
        "registered_at_invalid": "Вкажіть коректну дату та час.",
        "source_image_invalid": "Шлях до фото має бути текстом.",
        "record_missing": "Запис обладнання вже відсутній. Оновіть список.",
        "model_missing": "Модель уже відсутня. Оновіть список.",
        "model_name_required": "Введіть назву моделі.",
        "model_type_invalid": "Оберіть тип модем або тюнер.",
        "model_service_invalid": "Оберіть послугу інтернет або телебачення.",
    }
)

_en.update(
    {
        "shutdown_wait": "Finishing background operations before exiting…",
        "recognized_text_required": "Enter a serial number, MAC address or text.",
        "contract_invalid": "The contract number must be text.",
        "operation_invalid": "Select a receipt or issue operation.",
        "model_required": "Select an existing equipment model.",
        "registered_at_invalid": "Enter a valid date and time.",
        "source_image_invalid": "The photo path must be text.",
        "record_missing": "The equipment record no longer exists. Refresh the list.",
        "model_missing": "The model no longer exists. Refresh the list.",
        "model_name_required": "Enter the model name.",
        "model_type_invalid": "Select modem or tuner as the type.",
        "model_service_invalid": "Select internet or television as the service.",
    }
)
_pl.update(
    {
        "shutdown_wait": "Kończenie operacji w tle przed zamknięciem…",
        "recognized_text_required": "Wpisz numer seryjny, adres MAC lub tekst.",
        "contract_invalid": "Numer umowy musi być tekstem.",
        "operation_invalid": "Wybierz operację przyjęcia lub wydania.",
        "model_required": "Wybierz istniejący model sprzętu.",
        "registered_at_invalid": "Podaj prawidłową datę i godzinę.",
        "source_image_invalid": "Ścieżka zdjęcia musi być tekstem.",
        "record_missing": "Wpis sprzętu już nie istnieje. Odśwież listę.",
        "model_missing": "Model już nie istnieje. Odśwież listę.",
        "model_name_required": "Wpisz nazwę modelu.",
        "model_type_invalid": "Wybierz typ modem lub tuner.",
        "model_service_invalid": "Wybierz usługę internet lub telewizja.",
    }
)

TEXT = {"uk": _uk, "en": _en, "pl": _pl}

for _warehouse_locale, _warehouse_catalog in WAREHOUSE_TEXT.items():
    TEXT[_warehouse_locale].update(_warehouse_catalog)
for _locale, _values in TEXT.items():
    _values.setdefault("open", {"en": "Open", "pl": "Otwórz"}.get(_locale, "Відкрити"))
    _values.setdefault("exit", {"en": "Exit", "pl": "Wyjdź"}.get(_locale, "Вийти"))
    _values.setdefault("copy", {"en": "Copy", "pl": "Kopiuj"}.get(_locale, "Копіювати"))
    _values.setdefault(
        "add_to_database",
        {"en": "Add to database", "pl": "Dodaj do bazy"}.get(_locale, "Додати в БД"),
    )
    _values.setdefault(
        "add_raw_to_database",
        {"en": "Add unformatted to database", "pl": "Dodaj bez formatowania do bazy"}.get(
            _locale, "Додати в БД неформатовано"
        ),
    )
    _values.setdefault(
        "new_equipment",
        {"en": "New equipment record", "pl": "Nowy wpis sprzętu"}.get(
            _locale, "Новий запис обладнання"
        ),
    )
    _values.setdefault(
        "add_record", {"en": "Add record", "pl": "Dodaj wpis"}.get(_locale, "Додати запис")
    )
    _values.setdefault("edit", {"en": "Edit", "pl": "Edytuj"}.get(_locale, "Редагувати"))

_uk.update(
    {
        "first_run": "Перший запуск",
        "license_text": "Підтвердіть згоду з умовами та оберіть папку з фото.",
        "accept_and_continue": "Прийняти та продовжити",
        "startup_log": "Відкрити лог запуску",
        "check_updates": "Перевірити оновлення",
        "update_not_configured": "Перевірка оновлень ще не налаштована.",
    }
)

_en.update(
    {
        "first_run": "First launch",
        "license_text": "Accept the terms and select the image folder.",
        "accept_and_continue": "Accept and continue",
        "startup_log": "Open startup log",
        "check_updates": "Check for updates",
        "update_not_configured": "Update checking is not configured yet.",
    }
)
_pl.update(
    {
        "first_run": "Pierwsze uruchomienie",
        "license_text": "Zaakceptuj warunki i wybierz folder obrazów.",
        "accept_and_continue": "Akceptuj i kontynuuj",
        "startup_log": "Otwórz dziennik uruchamiania",
        "check_updates": "Sprawdź aktualizacje",
        "update_not_configured": "Sprawdzanie aktualizacji nie jest jeszcze skonfigurowane.",
    }
)

TEXT["uk"]["day"] = "По днях"

TEXT["en"]["day"] = "By day"
TEXT["pl"]["day"] = "Wedlug dni"
TEXT["uk"]["month"] = "По місяцях"
TEXT["en"]["month"] = "By month"
TEXT["pl"]["month"] = "Wedlug miesiecy"

TEXT["uk"]["github_repository"] = "GitHub-репозиторій оновлень"
TEXT["en"]["github_repository"] = "GitHub updates repository"
TEXT["pl"]["github_repository"] = "Repozytorium aktualizacji GitHub"
TEXT["uk"]["update_not_found"] = "Новішої версії не знайдено."
TEXT["en"]["update_not_found"] = "No newer version was found."
TEXT["pl"]["update_not_found"] = "Nie znaleziono nowszej wersji."

TEXT["uk"].update(
    {
        "license_acceptance": "Я приймаю умови використання",
        "license_required": "Потрібно підтвердити згоду з умовами.",
        "source_image_missing": "Файл вихідного фото вже не існує або недоступний.",
        "total": "Разом",
    }
)

TEXT["en"].update(
    {
        "license_acceptance": "I accept the terms of use",
        "license_required": "You must accept the terms.",
        "source_image_missing": "The linked photo no longer exists or is unavailable.",
        "total": "Total",
    }
)
TEXT["pl"].update(
    {
        "license_acceptance": "Akceptuje warunki uzytkowania",
        "license_required": "Musisz zaakceptowac warunki.",
        "source_image_missing": "Plik zrodlowego zdjecia juz nie istnieje lub jest niedostepny.",
        "total": "Razem",
    }
)

TEXT["uk"].update(
    {
        "contract_too_long": "Номер договору має містити до 20 символів.",
        "model_exists": "Модель з такою назвою, типом і послугою вже існує.",
        "model_in_use": "Не можна видалити модель, що використана у записах обладнання.",
    }
)

TEXT["en"].update(
    {
        "contract_too_long": "Contract number must not exceed 20 characters.",
        "model_exists": "A model with this name, type and service already exists.",
        "model_in_use": "A model linked to equipment records cannot be deleted.",
    }
)
TEXT["pl"].update(
    {
        "contract_too_long": "Numer umowy moze miec najwyzej 20 znakow.",
        "model_exists": "Model o tej nazwie, typie i usludze juz istnieje.",
        "model_in_use": "Nie mozna usunac modelu powiazanego z wpisami sprzetu.",
    }
)

TEXT["uk"].update({"previous_page": "Попередня сторінка", "next_page": "Наступна сторінка"})
TEXT["en"].update({"previous_page": "Previous page", "next_page": "Next page"})
TEXT["pl"].update({"previous_page": "Poprzednia strona", "next_page": "Nastepna strona"})

TEXT["uk"]["open_source_image"] = "Відкрити вихідне фото"
TEXT["en"]["open_source_image"] = "Open source image"
TEXT["pl"]["open_source_image"] = "Otworz zdjecie zrodlowe"

TEXT["uk"].update(
    {
        "menu_file": "Файл",
        "menu_edit": "Редагувати",
        "menu_view": "Вигляд",
        "help_contents": "Довідка",
        "help_text": "Оберіть фото, щоб автоматично запустити OCR і читання штрихкодів. Виділений результат можна скопіювати або додати до обліку через праву кнопку миші.",
        "select_text_to_copy": "Виділіть текст у полі результату, щоб скопіювати його.",
        "recognizing": "Виконується розпізнавання…",
        "interface_settings": "Інтерфейс",
        "folder_settings": "Папка зображень",
        "update_settings": "Оновлення",
        "save_interface": "Зберегти інтерфейс",
        "save_folder": "Зберегти папку",
        "save_updates": "Зберегти оновлення",
        "settings_saved": "Налаштування збережено.",
    }
)
TEXT["en"].update(
    {
        "menu_file": "File",
        "menu_edit": "Edit",
        "menu_view": "View",
        "help_contents": "Help",
        "help_text": "Select a photo to start OCR and barcode reading automatically. Right-click selected results to copy them or add them to equipment.",
        "select_text_to_copy": "Select text in a result field to copy it.",
        "recognizing": "Recognition in progress…",
        "interface_settings": "Interface",
        "folder_settings": "Image folder",
        "update_settings": "Updates",
        "save_interface": "Save interface",
        "save_folder": "Save folder",
        "save_updates": "Save updates",
        "settings_saved": "Settings saved.",
    }
)
TEXT["pl"].update(
    {
        "menu_file": "Plik",
        "menu_edit": "Edycja",
        "menu_view": "Widok",
        "help_contents": "Pomoc",
        "help_text": "Wybierz zdjęcie, aby automatycznie uruchomić OCR i odczyt kodów. Kliknij prawym przyciskiem zaznaczony wynik, aby go skopiować lub dodać do sprzętu.",
        "select_text_to_copy": "Zaznacz tekst w polu wyniku, aby go skopiować.",
        "recognizing": "Trwa rozpoznawanie…",
        "interface_settings": "Interfejs",
        "folder_settings": "Folder obrazów",
        "update_settings": "Aktualizacje",
        "save_interface": "Zapisz interfejs",
        "save_folder": "Zapisz folder",
        "save_updates": "Zapisz aktualizacje",
        "settings_saved": "Ustawienia zapisano.",
    }
)

TEXT["uk"]["open_image"] = "Відкрити зображення"
TEXT["en"]["open_image"] = "Open image"
TEXT["pl"]["open_image"] = "Otwórz obraz"

TEXT["uk"].update(
    {
        "automatic_update_unsupported": "Автоматичне оновлення доступне у встановленій версії SerialVision.exe. Зараз запущено dev-версію Python.",
        "update_integrity_failed": "Не вдалося перевірити цілісність завантаженого оновлення.",
        "update_checksum_unavailable": "Реліз не містить коректної контрольної суми SHA-256. Завантаження оновлення заблоковано. Спробуйте пізніше або зверніться до розробника.",
        "update_available_manual": "Доступна версія {version}. Встановіть її з опублікованих файлів релізу.",
    }
)
TEXT["en"].update(
    {
        "automatic_update_unsupported": "Automatic updates are available in the installed SerialVision.exe. The Python development version is running now.",
        "update_integrity_failed": "The downloaded update could not be verified.",
        "update_checksum_unavailable": "The release has no valid SHA-256 checksum. The update download has been blocked. Try again later or contact the developer.",
        "update_available_manual": "Version {version} is available. Install it from the release assets.",
    }
)
TEXT["pl"].update(
    {
        "automatic_update_unsupported": "Automatyczne aktualizacje są dostępne w zainstalowanym SerialVision.exe. Teraz działa wersja programistyczna Python.",
        "update_integrity_failed": "Nie można zweryfikować pobranej aktualizacji.",
        "update_checksum_unavailable": "Wydanie nie zawiera prawidłowej sumy kontrolnej SHA-256. Pobieranie aktualizacji zostało zablokowane. Spróbuj później lub skontaktuj się z programistą.",
        "update_available_manual": "Dostępna jest wersja {version}. Zainstaluj ją z plików wydania.",
    }
)

TEXT["uk"].update(
    {
        "run_ai": "Розпізнати AI",
        "ai_recognizing": "AI-розпізнавання виконується…",
        "edit_profile": "Редагувати профіль",
        "delete_profile": "Видалити вибраний AI-профіль?",
        "api_key_optional": "Залиште порожнім, щоб не змінювати ключ",
        "profile_key_required": "Заповніть назву, модель і API-ключ.",
        "ai_profile_missing": "AI-профіль не знайдено.",
    }
)
TEXT["en"].update(
    {
        "run_ai": "Run AI recognition",
        "ai_recognizing": "AI recognition in progress…",
        "edit_profile": "Edit profile",
        "delete_profile": "Delete the selected AI profile?",
        "api_key_optional": "Leave empty to keep the current key",
        "profile_key_required": "Enter a name, model and API key.",
        "ai_profile_missing": "AI profile was not found.",
    }
)
TEXT["pl"].update(
    {
        "run_ai": "Rozpoznaj AI",
        "ai_recognizing": "Trwa rozpoznawanie AI…",
        "edit_profile": "Edytuj profil",
        "delete_profile": "Usunąć wybrany profil AI?",
        "api_key_optional": "Pozostaw puste, aby zachować bieżący klucz",
        "profile_key_required": "Podaj nazwę, model i klucz API.",
        "ai_profile_missing": "Nie znaleziono profilu AI.",
    }
)

TEXT["uk"].update(
    {
        "appearance_settings": "Оформлення",
        "theme": "Тема",
        "theme_system": "Системна (за замовчуванням)",
        "theme_light": "Світла",
        "theme_dark": "Темна",
        "show_button_icons": "Показувати системні значки на кнопках",
        "save_appearance": "Зберегти оформлення",
    }
)
TEXT["en"].update(
    {
        "appearance_settings": "Appearance",
        "theme": "Theme",
        "theme_system": "System default",
        "theme_light": "Light",
        "theme_dark": "Dark",
        "show_button_icons": "Show system icons on buttons",
        "save_appearance": "Save appearance",
    }
)
TEXT["pl"].update(
    {
        "appearance_settings": "Wygląd",
        "theme": "Motyw",
        "theme_system": "Systemowy (domyślny)",
        "theme_light": "Jasny",
        "theme_dark": "Ciemny",
        "show_button_icons": "Pokazuj ikony systemowe na przyciskach",
        "save_appearance": "Zapisz wygląd",
    }
)

TEXT["uk"].update(
    {
        "icon_style": "Стиль значків",
        "icon_style_system": "Стандартні системні",
        "icon_style_modern": "Модерн",
        "icon_style_classic": "Класика",
        "icon_style_windows98": "Windows 98",
        "icon_style_ubuntu22": "Ubuntu 22",
        "add_model": "Додати модель",
        "edit_model": "Редагувати модель",
        "usage_count": "Кількість використань",
        "actions": "Дії",
    }
)
TEXT["en"].update(
    {
        "icon_style": "Icon style",
        "icon_style_system": "Standard system",
        "icon_style_modern": "Modern",
        "icon_style_classic": "Classic",
        "icon_style_windows98": "Windows 98",
        "icon_style_ubuntu22": "Ubuntu 22",
        "add_model": "Add model",
        "edit_model": "Edit model",
        "usage_count": "Usage count",
        "actions": "Actions",
    }
)
TEXT["pl"].update(
    {
        "icon_style": "Styl ikon",
        "icon_style_system": "Standardowy systemowy",
        "icon_style_modern": "Nowoczesny",
        "icon_style_classic": "Klasyczny",
        "icon_style_windows98": "Windows 98",
        "icon_style_ubuntu22": "Ubuntu 22",
        "add_model": "Dodaj model",
        "edit_model": "Edytuj model",
        "usage_count": "Liczba użyć",
        "actions": "Działania",
    }
)

TEXT["uk"].update(
    {
        "about_description": "Локальний застосунок для обліку обладнання та розпізнавання серійних номерів.",
        "developer_label": "Розробник",
        "website": "Сайт",
        "open_website": "Відкрити сайт",
        "close": "Закрити",
    }
)
TEXT["en"].update(
    {
        "about_description": "Local application for equipment tracking and serial-number recognition.",
        "developer_label": "Developer",
        "website": "Website",
        "open_website": "Open website",
        "close": "Close",
    }
)
TEXT["pl"].update(
    {
        "about_description": "Lokalna aplikacja do ewidencji sprzętu i rozpoznawania numerów seryjnych.",
        "developer_label": "Twórca",
        "website": "Strona internetowa",
        "open_website": "Otwórz stronę",
        "close": "Zamknij",
    }
)

TEXT["uk"]["open_file_failed"] = "Не вдалося відкрити файл: {error}"
TEXT["en"]["open_file_failed"] = "Could not open the file: {error}"
TEXT["pl"]["open_file_failed"] = "Nie można otworzyć pliku: {error}"

TEXT["uk"]["startup_log_unavailable"] = (
    "Не вдалося записати лог запуску у папку: {path}\nПричина ОС: {error}"
)
TEXT["en"]["startup_log_unavailable"] = (
    "Could not write the startup log to: {path}\nOS reason: {error}"
)
TEXT["pl"]["startup_log_unavailable"] = (
    "Nie można zapisać dziennika uruchomienia w folderze: {path}\nPrzyczyna systemowa: {error}"
)

TEXT["uk"]["open_help_section"] = "Відкрити довідку: {section}"
TEXT["en"]["open_help_section"] = "Open help: {section}"
TEXT["pl"]["open_help_section"] = "Otwórz pomoc: {section}"

TEXT["uk"].update(
    {
        "api_integrations": "API-інтеграції",
        "api_enabled": "Увімкнути локальний API (127.0.0.1)",
        "api_port": "Порт API",
        "api_rate": "Ліміт запитів на ключ",
        "api_rate_5": "5 запитів за секунду",
        "api_rate_2": "2 запити за секунду",
        "api_rate_1": "1 запит за секунду",
        "api_rate_half": "1 запит за 2 секунди",
        "save_api": "Зберегти API",
        "api_keys": "Bearer-ключі",
        "note": "Примітка",
        "api_key_prefix": "Префікс",
        "expires_at": "Діє до",
        "api_status": "Статус",
        "api_active": "Активний",
        "api_revoked": "Відкликаний",
        "issue_api_key": "Випустити ключ",
        "revoke_api_key": "Відкликати ключ",
        "revoke_api_key_confirm": "Відкликати вибраний API-ключ?",
        "api_key_expiry": "Обмежити строк дії",
        "api_key_created": "API-ключ створено",
        "api_key_once": "Скопіюйте ключ зараз. Пізніше його переглянути неможливо.",
        "api_key_name_required": "Вкажіть назву API-ключа.",
        "api_port_invalid": "Порт має бути від 1024 до 65535.",
        "api_rate_invalid": "Непідтримуваний ліміт запитів.",
        "api_start_failed": "Не вдалося запустити локальний API: {error}",
        "api_audit": "Журнал API-операцій",
        "method": "Метод",
        "path": "Шлях",
        "status": "Статус",
        "never": "Безстроково",
    }
)

TEXT["en"].update(
    {
        "api_integrations": "API integrations",
        "api_enabled": "Enable local API (127.0.0.1)",
        "api_port": "API port",
        "api_rate": "Request limit per key",
        "api_rate_5": "5 requests per second",
        "api_rate_2": "2 requests per second",
        "api_rate_1": "1 request per second",
        "api_rate_half": "1 request per 2 seconds",
        "save_api": "Save API",
        "api_keys": "Bearer keys",
        "note": "Note",
        "api_key_prefix": "Prefix",
        "expires_at": "Expires at",
        "api_status": "Status",
        "api_active": "Active",
        "api_revoked": "Revoked",
        "issue_api_key": "Issue key",
        "revoke_api_key": "Revoke key",
        "revoke_api_key_confirm": "Revoke selected API key?",
        "api_key_expiry": "Limit validity period",
        "api_key_created": "API key created",
        "api_key_once": "Copy this key now. It cannot be viewed later.",
        "api_key_name_required": "Enter an API key name.",
        "api_port_invalid": "Port must be between 1024 and 65535.",
        "api_rate_invalid": "Unsupported request limit.",
        "api_start_failed": "Could not start local API: {error}",
        "api_audit": "API operation log",
        "method": "Method",
        "path": "Path",
        "status": "Status",
        "never": "Never",
    }
)
TEXT["pl"].update(
    {
        "api_integrations": "Integracje API",
        "api_enabled": "Włącz lokalne API (127.0.0.1)",
        "api_port": "Port API",
        "api_rate": "Limit żądań na klucz",
        "api_rate_5": "5 żądań na sekundę",
        "api_rate_2": "2 żądania na sekundę",
        "api_rate_1": "1 żądanie na sekundę",
        "api_rate_half": "1 żądanie na 2 sekundy",
        "save_api": "Zapisz API",
        "api_keys": "Klucze Bearer",
        "note": "Notatka",
        "api_key_prefix": "Prefiks",
        "expires_at": "Wygasa",
        "api_status": "Status",
        "api_active": "Aktywny",
        "api_revoked": "Cofnięty",
        "issue_api_key": "Wydaj klucz",
        "revoke_api_key": "Cofnij klucz",
        "revoke_api_key_confirm": "Cofnąć wybrany klucz API?",
        "api_key_expiry": "Ogranicz okres ważności",
        "api_key_created": "Utworzono klucz API",
        "api_key_once": "Skopiuj klucz teraz. Później nie można go wyświetlić.",
        "api_key_name_required": "Podaj nazwę klucza API.",
        "api_port_invalid": "Port musi być od 1024 do 65535.",
        "api_rate_invalid": "Nieobsługiwany limit żądań.",
        "api_start_failed": "Nie można uruchomić lokalnego API: {error}",
        "api_audit": "Dziennik operacji API",
        "method": "Metoda",
        "path": "Ścieżka",
        "status": "Status",
        "never": "Bezterminowo",
    }
)

TEXT["uk"]["version_label"] = "Версія"
TEXT["en"]["version_label"] = "Version"
TEXT["pl"]["version_label"] = "Wersja"

TEXT["uk"].update(
    {
        "import_models": "Імпорт моделей з Excel",
        "model_import_summary": "Додано: {added}. Пропущено дублікатів: {duplicates}. Некоректних рядків: {invalid}.",
        "model_import_file_type": "Оберіть файл Excel у форматі .xlsx.",
        "model_import_file_invalid": "Не вдалося прочитати файл Excel.",
        "model_import_headers": "Excel має містити колонки name, device_type, service.",
    }
)
TEXT["en"].update(
    {
        "import_models": "Import models from Excel",
        "model_import_summary": "Added: {added}. Duplicate rows skipped: {duplicates}. Invalid rows: {invalid}.",
        "model_import_file_type": "Choose an Excel .xlsx file.",
        "model_import_file_invalid": "The Excel file could not be read.",
        "model_import_headers": "Excel must contain name, device_type and service columns.",
    }
)
TEXT["pl"].update(
    {
        "import_models": "Importuj modele z Excel",
        "model_import_summary": "Dodano: {added}. Pominięto duplikaty: {duplicates}. Niepoprawne wiersze: {invalid}.",
        "model_import_file_type": "Wybierz plik Excel .xlsx.",
        "model_import_file_invalid": "Nie można odczytać pliku Excel.",
        "model_import_headers": "Excel musi zawierać kolumny name, device_type i service.",
    }
)

TEXT["uk"].update(
    {
        "generate_qr": "Отримати QR-код",
        "generate_barcode": "Отримати штрихкод",
        "code_preview": "Перегляд коду",
        "qrcode_title": "QR-код: {code}",
        "barcode_title": "Штрихкод Code 128: {code}",
        "save_png": "Зберегти PNG",
        "code_value_empty": "Введіть серійний номер, MAC-адресу або текст для створення коду.",
        "code_type_invalid": "Непідтримуваний тип коду.",
        "code_save_failed": "Не вдалося зберегти PNG: {error}",
    }
)
TEXT["en"].update(
    {
        "generate_qr": "Get QR code",
        "generate_barcode": "Get barcode",
        "code_preview": "Code preview",
        "qrcode_title": "QR code: {code}",
        "barcode_title": "Code 128 barcode: {code}",
        "save_png": "Save PNG",
        "code_value_empty": "Enter a serial number, MAC address, or text to create a code.",
        "code_type_invalid": "Unsupported code type.",
        "code_save_failed": "Could not save PNG: {error}",
    }
)
TEXT["pl"].update(
    {
        "generate_qr": "Uzyskaj kod QR",
        "generate_barcode": "Uzyskaj kod kreskowy",
        "code_preview": "Podgląd kodu",
        "qrcode_title": "Kod QR: {code}",
        "barcode_title": "Kod kreskowy Code 128: {code}",
        "save_png": "Zapisz PNG",
        "code_value_empty": "Wprowadź numer seryjny, adres MAC lub tekst, aby utworzyć kod.",
        "code_type_invalid": "Nieobsługiwany typ kodu.",
        "code_save_failed": "Nie można zapisać PNG: {error}",
    }
)

TEXT["uk"].update(
    {
        "scan": "Відсканувати",
        "camera": "Камера",
        "camera_refresh": "Оновити камери",
        "camera_start": "Запустити камеру",
        "camera_stop": "Зупинити камеру",
        "camera_capture": "Зробити кадр",
        "camera_select": "Оберіть камеру та запустіть її.",
        "camera_unavailable": "Камера не знайдена або недоступна.",
        "camera_ready": "Камеру запущено. Зробіть кадр для локального розпізнавання.",
        "camera_stopped": "Камеру зупинено.",
        "camera_capturing": "Захоплення кадру…",
        "camera_result": "Результат сканування",
        "camera_result_empty": "QR або штрихкод не знайдено.",
        "camera_error": "Помилка камери: {error}",
        "copy_record": "Копіювати запис",
        "api_request_examples": "Побачити API-запит",
    }
)
TEXT["en"].update(
    {
        "scan": "Scan",
        "camera": "Camera",
        "camera_refresh": "Refresh cameras",
        "camera_start": "Start camera",
        "camera_stop": "Stop camera",
        "camera_capture": "Capture frame",
        "camera_select": "Select a camera and start it.",
        "camera_unavailable": "No camera is available.",
        "camera_ready": "Camera is running. Capture a frame for local recognition.",
        "camera_stopped": "Camera stopped.",
        "camera_capturing": "Capturing frame…",
        "camera_result": "Scan result",
        "camera_result_empty": "No QR code or barcode was found.",
        "camera_error": "Camera error: {error}",
        "copy_record": "Copy record",
        "api_request_examples": "View API request",
    }
)
TEXT["pl"].update(
    {
        "scan": "Skanuj",
        "camera": "Kamera",
        "camera_refresh": "Odśwież kamery",
        "camera_start": "Uruchom kamerę",
        "camera_stop": "Zatrzymaj kamerę",
        "camera_capture": "Zrób zdjęcie",
        "camera_select": "Wybierz kamerę i uruchom ją.",
        "camera_unavailable": "Kamera nie jest dostępna.",
        "camera_ready": "Kamera działa. Zrób zdjęcie do lokalnego rozpoznania.",
        "camera_stopped": "Kamera została zatrzymana.",
        "camera_capturing": "Robienie zdjęcia…",
        "camera_result": "Wynik skanowania",
        "camera_result_empty": "Nie znaleziono kodu QR ani kreskowego.",
        "camera_error": "Błąd kamery: {error}",
        "copy_record": "Kopiuj wpis",
        "api_request_examples": "Pokaż żądanie API",
    }
)
TEXT["uk"].update(
    {
        "application_already_running": "Advanced Serial Vision уже запущено. Закрийте наявне вікно або скористайтеся значком у системному треї.",
        "update_available_notice": "Доступне оновлення v{version}. Оберіть «Довідка → Перевірити оновлення», щоб переглянути зміни та підтвердити встановлення.",
        "update_available_title": "Доступне оновлення v{version}",
        "update_available_details": "Вийшла нова версія v{version}. Установіть її зараз або пропустіть — застосунок не завантажуватиме й не встановлюватиме нічого без вашої дії.",
        "update_release_notes": "Що змінилося",
        "download_and_install": "Завантажити й установити",
        "download_deb": "Завантажити DEB",
        "open_release": "Відкрити сторінку релізу",
        "later": "Пізніше",
        "update_no_changelog": "Опис змін недоступний.",
        "update_downloading": "Завантаження та перевірка оновлення v{version}…",
        "update_download_failed": "Не вдалося завантажити оновлення: {error}",
        "linux_update_ready": "DEB-пакет завантажено: {path}\n\nЙого відкрито у системному інсталяторі. Підтвердіть встановлення там; ОС за потреби попросить закрити застосунок.",
        "linux_update_open_failed": "DEB-пакет завантажено до {path}, але не вдалося відкрити системний інсталятор. Відкрийте цей файл вручну.",
    }
)
TEXT["en"].update(
    {
        "application_already_running": "Advanced Serial Vision is already running. Close the existing window or use the system-tray icon.",
        "update_available_notice": "Update v{version} is available. Choose Help → Check for updates to review changes and confirm installation.",
        "update_available_title": "Update v{version} is available",
        "update_available_details": "A new version v{version} is available. Install it now or skip it—the application will not download or install anything without your action.",
        "update_release_notes": "What changed",
        "download_and_install": "Download and install",
        "download_deb": "Download DEB",
        "open_release": "Open release page",
        "later": "Later",
        "update_no_changelog": "The change description is unavailable.",
        "update_downloading": "Downloading and verifying update v{version}…",
        "update_download_failed": "Could not download the update: {error}",
        "linux_update_ready": "The DEB package was downloaded to: {path}\n\nIt has been opened in the system installer. Confirm installation there; the OS may ask you to close the application.",
        "linux_update_open_failed": "The DEB package was downloaded to {path}, but the system installer could not be opened. Open this file manually.",
    }
)
TEXT["pl"].update(
    {
        "application_already_running": "Advanced Serial Vision jest już uruchomiony. Zamknij istniejące okno lub użyj ikony w zasobniku systemowym.",
        "update_available_notice": "Dostępna jest aktualizacja v{version}. Wybierz Pomoc → Sprawdź aktualizacje, aby zobaczyć zmiany i potwierdzić instalację.",
        "update_available_title": "Dostępna jest aktualizacja v{version}",
        "update_available_details": "Dostępna jest nowa wersja v{version}. Zainstaluj ją teraz lub pomiń — aplikacja niczego nie pobierze ani nie zainstaluje bez Twojego działania.",
        "update_release_notes": "Co się zmieniło",
        "download_and_install": "Pobierz i zainstaluj",
        "download_deb": "Pobierz DEB",
        "open_release": "Otwórz stronę wydania",
        "later": "Później",
        "update_no_changelog": "Opis zmian jest niedostępny.",
        "update_downloading": "Pobieranie i sprawdzanie aktualizacji v{version}…",
        "update_download_failed": "Nie można pobrać aktualizacji: {error}",
        "linux_update_ready": "Pakiet DEB pobrano do: {path}\n\nZostał otwarty w instalatorze systemowym. Potwierdź instalację tam; system może poprosić o zamknięcie aplikacji.",
        "linux_update_open_failed": "Pakiet DEB pobrano do {path}, ale nie można otworzyć instalatora systemowego. Otwórz ten plik ręcznie.",
    }
)

TEXT["uk"].update(
    {
        "update_progress_title": "Оновлення v{version}",
        "update_step_download": "1. Завантаження оновлення",
        "update_step_prepare": "2. Перевірка та запуск інсталятора",
        "update_step_close": "3. Закриття застосунку для оновлення",
        "update_source": "Джерело: {url}",
        "update_source_unknown": "адреса недоступна",
        "update_download_starting": "Підготовка завантаження…",
        "update_download_status": "Завантажено {downloaded} із {total} MiB ({percent}%).",
        "update_download_status_unknown": "Завантажено {downloaded} MiB.",
        "update_verifying": "Файл завантажено. Перевіряється його цілісність…",
        "update_closing_application": "Інсталятор підготовлено. Застосунок закриється, після чого відкриється видимий майстер встановлення.",
        "show_update_log": "Показати журнал",
        "hide_update_log": "Сховати журнал",
        "open_update_log": "Відкрити файл журналу",
        "update_log_open_failed": "Не вдалося відкрити журнал оновлення: {path}",
    }
)
TEXT["en"].update(
    {
        "update_progress_title": "Update v{version}",
        "update_step_download": "1. Downloading the update",
        "update_step_prepare": "2. Verifying and starting the installer",
        "update_step_close": "3. Closing the application for update",
        "update_source": "Source: {url}",
        "update_source_unknown": "address unavailable",
        "update_download_starting": "Preparing download…",
        "update_download_status": "Downloaded {downloaded} of {total} MiB ({percent}%).",
        "update_download_status_unknown": "Downloaded {downloaded} MiB.",
        "update_verifying": "The file is downloaded. Verifying its integrity…",
        "update_closing_application": "The installer is ready. The application will close and the visible setup wizard will open.",
        "show_update_log": "Show log",
        "hide_update_log": "Hide log",
        "open_update_log": "Open log file",
        "update_log_open_failed": "Could not open the update log: {path}",
    }
)
TEXT["pl"].update(
    {
        "update_progress_title": "Aktualizacja v{version}",
        "update_step_download": "1. Pobieranie aktualizacji",
        "update_step_prepare": "2. Sprawdzanie i uruchamianie instalatora",
        "update_step_close": "3. Zamykanie aplikacji do aktualizacji",
        "update_source": "Źródło: {url}",
        "update_source_unknown": "adres niedostępny",
        "update_download_starting": "Przygotowywanie pobierania…",
        "update_download_status": "Pobrano {downloaded} z {total} MiB ({percent}%).",
        "update_download_status_unknown": "Pobrano {downloaded} MiB.",
        "update_verifying": "Plik został pobrany. Trwa sprawdzanie integralności…",
        "update_closing_application": "Instalator jest gotowy. Aplikacja zostanie zamknięta, a widoczny kreator instalacji zostanie otwarty.",
        "show_update_log": "Pokaż dziennik",
        "hide_update_log": "Ukryj dziennik",
        "open_update_log": "Otwórz plik dziennika",
        "update_log_open_failed": "Nie można otworzyć dziennika aktualizacji: {path}",
    }
)

TEXT["uk"]["barcode_ocr_fallback"] = "Текст етикетки (OCR)"
TEXT["en"]["barcode_ocr_fallback"] = "Label text (OCR)"
TEXT["pl"]["barcode_ocr_fallback"] = "Tekst etykiety (OCR)"

TEXT["uk"].update(
    {
        "recognition_strategies": "Стратегії розпізнавання",
        "recognition_original_info": "Оригінальне фото (старий алгоритм) перевіряється завжди першим.",
        "recognition_rotate": "Автоматично перевіряти повороти 90°, 180° і 270°",
        "recognition_enhance": "Додатково обробляти розмиті та слабоконтрастні фото",
        "save_recognition_strategies": "Зберегти стратегії",
    }
)
TEXT["en"].update(
    {
        "recognition_strategies": "Recognition strategies",
        "recognition_original_info": "The original photo (previous algorithm) is always checked first.",
        "recognition_rotate": "Automatically try 90°, 180° and 270° rotations",
        "recognition_enhance": "Also process blurred and low-contrast photos",
        "save_recognition_strategies": "Save strategies",
    }
)
TEXT["pl"].update(
    {
        "recognition_strategies": "Strategie rozpoznawania",
        "recognition_original_info": "Oryginalne zdjęcie (poprzedni algorytm) jest zawsze sprawdzane jako pierwsze.",
        "recognition_rotate": "Automatycznie sprawdzaj obroty 90°, 180° i 270°",
        "recognition_enhance": "Dodatkowo przetwarzaj rozmyte zdjęcia o niskim kontraście",
        "save_recognition_strategies": "Zapisz strategie",
    }
)
TEXT["uk"]["barcode_module_unavailable"] = "Модуль розпізнавання штрихкодів не встановлено."
TEXT["en"]["barcode_module_unavailable"] = "The barcode recognition module is not installed."
TEXT["pl"]["barcode_module_unavailable"] = (
    "Moduł rozpoznawania kodów kreskowych nie jest zainstalowany."
)

TEXT["uk"].update(
    {
        "fit_image": "Вмістити",
        "actual_size": "100%",
        "image_preview": "Перегляд вибраного фото",
        "preview_zoom_hint": "Прокручуйте коліщатко над фото для зміни масштабу; перетягуйте фото для огляду.",
        "retry_recognition": "Розпізнати повторно",
        "cancel_recognition": "Скасувати",
        "recognition_ready": "Оберіть фото для розпізнавання.",
        "recognition_step_ocr": "Крок 1/2: розпізнавання тексту OCR…",
        "recognition_step_barcode": "Крок 2/2: читання штрихкодів…",
        "recognition_cancelling": "Скасування після завершення поточного етапу…",
        "recognition_cancelled": "Розпізнавання скасовано.",
        "recognition_finished": "Розпізнавання завершено.",
        "date_from_label": "Дата від",
        "date_to_label": "Дата до",
        "save_settings": "Зберегти налаштування",
        "settings_unsaved": "Є незбережені зміни.",
    }
)
TEXT["en"].update(
    {
        "fit_image": "Fit",
        "actual_size": "100%",
        "image_preview": "Selected photo preview",
        "preview_zoom_hint": "Use the mouse wheel over the photo to zoom; drag the photo to pan.",
        "retry_recognition": "Recognize again",
        "cancel_recognition": "Cancel",
        "recognition_ready": "Select a photo to recognize.",
        "recognition_step_ocr": "Step 1/2: recognizing text with OCR…",
        "recognition_step_barcode": "Step 2/2: reading barcodes…",
        "recognition_cancelling": "Stopping after the current stage finishes…",
        "recognition_cancelled": "Recognition cancelled.",
        "recognition_finished": "Recognition complete.",
        "date_from_label": "Date from",
        "date_to_label": "Date to",
        "save_settings": "Save settings",
        "settings_unsaved": "You have unsaved changes.",
    }
)
TEXT["pl"].update(
    {
        "fit_image": "Dopasuj",
        "actual_size": "100%",
        "image_preview": "Podgląd wybranego zdjęcia",
        "preview_zoom_hint": "Użyj kółka myszy nad zdjęciem, aby zmienić skalę; przeciągnij zdjęcie, aby je przesunąć.",
        "retry_recognition": "Rozpoznaj ponownie",
        "cancel_recognition": "Anuluj",
        "recognition_ready": "Wybierz zdjęcie do rozpoznania.",
        "recognition_step_ocr": "Krok 1/2: rozpoznawanie tekstu OCR…",
        "recognition_step_barcode": "Krok 2/2: odczytywanie kodów kreskowych…",
        "recognition_cancelling": "Zatrzymywanie po zakończeniu bieżącego etapu…",
        "recognition_cancelled": "Rozpoznawanie anulowano.",
        "recognition_finished": "Rozpoznawanie zakończone.",
        "date_from_label": "Data od",
        "date_to_label": "Data do",
        "save_settings": "Zapisz ustawienia",
        "settings_unsaved": "Masz niezapisane zmiany.",
    }
)

TEXT["uk"].update(
    {
        "editor": "Редактор фото",
        "image_editor_title": "Редактор фото для розпізнавання",
        "editor_reset": "Скинути правки",
        "editor_crop": "Обрізання",
        "editor_x": "X",
        "editor_y": "Y",
        "editor_width": "Ширина",
        "editor_height": "Висота",
        "editor_apply_crop": "Обрізати",
        "editor_crop_invalid": "Перевірте координати: область має бути всередині фото й не меншою за 2 × 2 пікселі.",
        "editor_resize_percent": "Масштаб зображення",
        "editor_apply_resize": "Змінити розмір",
        "editor_resize_invalid": "Після зміни розміру зображення завелике. Зменште відсоток або спершу обріжте фото.",
        "editor_rotation_angle": "Кут повороту",
        "editor_apply_rotation": "Повернути на кут",
        "editor_rotation_invalid": "Фото після повороту завелике. Спершу зменште його розмір.",
        "editor_advanced": "Додаткові налаштування",
        "editor_brightness": "Яскравість",
        "editor_contrast": "Контрастність",
        "editor_color": "Насиченість кольору",
        "editor_sharpness": "Різкість",
        "editor_crop_preview": "Фото з областю обрізання",
        "editor_crop_hint": "Протягніть мишею для виділення. Тягніть краї чи кути рамки, щоб змінити розмір, або всередині рамки, щоб перемістити її. Точка над фото повертає весь кадр. Для точності введіть X, Y, ширину й висоту вручну.",
        "editor_dimensions": "Розмір робочого фото: {width} × {height} пікселів. Оригінал не змінюється.",
        "editor_ai_profile": "AI-профіль",
        "editor_no_ai": "Без AI (локально)",
        "editor_ai_not_selected": "AI не вибрано — фото не надсилається в мережу.",
        "editor_ai_waiting": "AI запуститься після локального розпізнавання…",
        "editor_stage_ocr_ai": "Крок 1/3: розпізнавання тексту OCR…",
        "editor_stage_barcode_ai": "Крок 2/3: читання штрихкодів…",
        "editor_ai_stage": "Крок 3/3: AI-розпізнавання…",
        "editor_ai_failed": "AI-розпізнавання не вдалося; локальні результати збережено.",
        "editor_recognize": "Розпізнати",
        "editor_ready": "Оберіть область та налаштуйте фото, потім натисніть «Розпізнати».",
        "editor_preview_failed": "Не вдалося показати попередній перегляд.",
        "editor_snapshot_failed": "Не вдалося підготувати фото для розпізнавання: {error}",
    }
)
TEXT["en"].update(
    {
        "editor": "Photo editor",
        "image_editor_title": "Photo editor for recognition",
        "editor_reset": "Reset edits",
        "editor_crop": "Crop",
        "editor_x": "X",
        "editor_y": "Y",
        "editor_width": "Width",
        "editor_height": "Height",
        "editor_apply_crop": "Crop",
        "editor_crop_invalid": "Check the coordinates: the region must be inside the photo and at least 2 × 2 pixels.",
        "editor_resize_percent": "Image scale",
        "editor_apply_resize": "Resize",
        "editor_resize_invalid": "The resized image would be too large. Lower the percentage or crop it first.",
        "editor_rotation_angle": "Rotation angle",
        "editor_apply_rotation": "Rotate by angle",
        "editor_rotation_invalid": "The rotated photo would be too large. Resize it smaller first.",
        "editor_advanced": "Advanced adjustments",
        "editor_brightness": "Brightness",
        "editor_contrast": "Contrast",
        "editor_color": "Color saturation",
        "editor_sharpness": "Sharpness",
        "editor_crop_preview": "Photo with crop selection",
        "editor_crop_hint": "Drag to select a region. Drag its edges or corners to resize it, or drag inside to move it. The dot above the photo rotates the entire image. For precision, enter X, Y, width and height manually.",
        "editor_dimensions": "Working photo: {width} × {height} pixels. The original is unchanged.",
        "editor_ai_profile": "AI profile",
        "editor_no_ai": "No AI (local only)",
        "editor_ai_not_selected": "AI is not selected — the photo is not sent online.",
        "editor_ai_waiting": "AI will start after local recognition…",
        "editor_stage_ocr_ai": "Step 1/3: recognizing text with OCR…",
        "editor_stage_barcode_ai": "Step 2/3: reading barcodes…",
        "editor_ai_stage": "Step 3/3: AI recognition…",
        "editor_ai_failed": "AI recognition failed; local results are preserved.",
        "editor_recognize": "Recognize",
        "editor_ready": "Choose a region and adjust the photo, then select Recognize.",
        "editor_preview_failed": "The preview could not be displayed.",
        "editor_snapshot_failed": "Could not prepare the photo for recognition: {error}",
    }
)
TEXT["pl"].update(
    {
        "editor": "Edytor zdjęć",
        "image_editor_title": "Edytor zdjęć do rozpoznawania",
        "editor_reset": "Cofnij zmiany",
        "editor_crop": "Kadrowanie",
        "editor_x": "X",
        "editor_y": "Y",
        "editor_width": "Szerokość",
        "editor_height": "Wysokość",
        "editor_apply_crop": "Przytnij",
        "editor_crop_invalid": "Sprawdź współrzędne: obszar musi mieścić się w zdjęciu i mieć co najmniej 2 × 2 piksele.",
        "editor_resize_percent": "Skala obrazu",
        "editor_apply_resize": "Zmień rozmiar",
        "editor_resize_invalid": "Obraz po zmianie rozmiaru byłby zbyt duży. Zmniejsz procent lub najpierw go przytnij.",
        "editor_rotation_angle": "Kąt obrotu",
        "editor_apply_rotation": "Obróć o kąt",
        "editor_rotation_invalid": "Zdjęcie po obrocie byłoby zbyt duże. Najpierw zmniejsz jego rozmiar.",
        "editor_advanced": "Ustawienia zaawansowane",
        "editor_brightness": "Jasność",
        "editor_contrast": "Kontrast",
        "editor_color": "Nasycenie kolorów",
        "editor_sharpness": "Ostrość",
        "editor_crop_preview": "Zdjęcie z zaznaczeniem kadrowania",
        "editor_crop_hint": "Przeciągnij, aby zaznaczyć obszar. Przeciągaj krawędzie lub narożniki ramki, aby zmienić jej rozmiar, albo wnętrze, aby ją przesunąć. Punkt nad zdjęciem obraca cały obraz. Dla precyzji wpisz ręcznie X, Y, szerokość i wysokość.",
        "editor_dimensions": "Rozmiar roboczy: {width} × {height} pikseli. Oryginał pozostaje bez zmian.",
        "editor_ai_profile": "Profil AI",
        "editor_no_ai": "Bez AI (tylko lokalnie)",
        "editor_ai_not_selected": "Nie wybrano AI — zdjęcie nie jest wysyłane do sieci.",
        "editor_ai_waiting": "AI uruchomi się po lokalnym rozpoznawaniu…",
        "editor_stage_ocr_ai": "Krok 1/3: rozpoznawanie tekstu OCR…",
        "editor_stage_barcode_ai": "Krok 2/3: odczytywanie kodów kreskowych…",
        "editor_ai_stage": "Krok 3/3: rozpoznawanie AI…",
        "editor_ai_failed": "Rozpoznawanie AI nie powiodło się; wyniki lokalne zachowano.",
        "editor_recognize": "Rozpoznaj",
        "editor_ready": "Wybierz obszar i dostosuj zdjęcie, a następnie naciśnij Rozpoznaj.",
        "editor_preview_failed": "Nie można wyświetlić podglądu.",
        "editor_snapshot_failed": "Nie można przygotować zdjęcia do rozpoznawania: {error}",
    }
)

TEXT["uk"].update(
    {
        "ocr_no_text": "OCR не знайшов текст на цьому зображенні.",
        "statistics_group_invalid": "Оберіть групування за днем або місяцем.",
        "settings_save_failed": "Не вдалося зберегти налаштування: {error}",
        "settings_invalid": "Перевірте мову, тему та стиль іконок.",
        "settings_api_restore_failed": "Налаштування не збережено, і попередній стан API не вдалося відновити. Перевірте доступність порту та повторіть збереження.",
        "api_bearer_required": "Потрібен Bearer-токен.",
        "api_key_invalid": "API-ключ недійсний або відкликаний.",
        "api_key_expired": "Строк дії API-ключа минув.",
        "api_rate_exceeded": "Перевищено ліміт запитів. Повторіть спробу пізніше.",
        "editor_rotation_range": "Кут повороту має бути від −180 до 180 градусів.",
        "editor_resize_range": "Масштаб має бути від 25 до 300 відсотків.",
        "editor_adjustment_range": "Значення налаштувань зображення мають бути від 0 до 200.",
        "image_outside_folder": "Зображення знаходиться поза вибраною папкою.",
        "splitter_unknown": "Невідомий розділювач панелей.",
        "ai_no_text": "AI-постачальник не повернув розпізнаного тексту.",
        "startup_log_retry": "Повторна спроба запису журналу запуску після помилки доступу.",
        "updater_title": "Advanced Serial Vision — оновлювач",
        "updater_heading": "Окремий оновлювач для попередніх версій Advanced Serial Vision",
        "updater_language": "Мова інтерфейсу",
        "updater_system_language": "Автоматично (мова ОС)",
        "updater_ready": "Готово до перевірки оновлення.",
        "updater_install": "Завантажити та запустити інсталятор",
        "updater_close": "Закрити",
        "updater_log": "Журнал процесу",
        "updater_checking": "Перевірка останнього релізу…",
        "updater_request": "Запит до GitHub Releases.",
        "updater_downloading": "Завантаження v{version}…",
        "updater_source": "Джерело: {url}",
        "updater_verified": "Файл перевірено. Відкривається інсталятор…",
        "updater_verified_path": "SHA-256 перевірено: {path}",
        "updater_done": "Інсталятор запущено. Підтвердіть оновлення у його вікні; він закриє старий Serial Vision за потреби.",
        "updater_error_status": "Оновлення не виконано.",
        "updater_error_log": "Помилка: {error}",
        "updater_error_dialog": "Не вдалося підготувати оновлення:\n{error}",
        "updater_downloaded": "Завантажено {done} з {total} MiB ({percent}%).",
        "updater_download_unknown": "Завантажено {done} MiB…",
        "updater_no_installer": "У поточному релізі не знайдено Windows EXE-інсталятора.",
        "updater_no_digest": "GitHub Release не містить SHA-256 для інсталятора; завантаження скасовано.",
        "updater_digest_mismatch": "SHA-256 інсталятора не збігається з даними GitHub Release.",
        "updater_windows_only": "Цей оновлювач призначений лише для Windows.",
    }
)

TEXT["en"].update(
    {
        "ocr_no_text": "OCR found no text in this image.",
        "statistics_group_invalid": "Select daily or monthly grouping.",
        "settings_save_failed": "Could not save settings: {error}",
        "settings_invalid": "Check the language, theme and icon style.",
        "settings_api_restore_failed": "Settings were not saved and the previous API configuration could not be restored. Check port availability and save again.",
        "api_bearer_required": "Bearer token required.",
        "api_key_invalid": "Invalid or revoked API key.",
        "api_key_expired": "API key has expired.",
        "api_rate_exceeded": "Rate limit exceeded. Try again later.",
        "editor_rotation_range": "Rotation must be between −180 and 180 degrees.",
        "editor_resize_range": "Resize percentage must be between 25 and 300.",
        "editor_adjustment_range": "Image adjustments must be between 0 and 200.",
        "image_outside_folder": "The image is outside the selected folder.",
        "splitter_unknown": "Unknown panel splitter.",
        "ai_no_text": "The AI provider returned no recognized text.",
        "startup_log_retry": "Retrying startup log after an access error.",
        "updater_title": "Advanced Serial Vision — updater",
        "updater_heading": "Standalone updater for earlier versions of Advanced Serial Vision",
        "updater_language": "Interface language",
        "updater_system_language": "Automatic (system language)",
        "updater_ready": "Ready to check for updates.",
        "updater_install": "Download and run installer",
        "updater_close": "Close",
        "updater_log": "Process log",
        "updater_checking": "Checking the latest release…",
        "updater_request": "Requesting GitHub Releases.",
        "updater_downloading": "Downloading v{version}…",
        "updater_source": "Source: {url}",
        "updater_verified": "File verified. Opening the installer…",
        "updater_verified_path": "SHA-256 verified: {path}",
        "updater_done": "Installer started. Confirm the update in its window; it will close the old Serial Vision if needed.",
        "updater_error_status": "Update was not completed.",
        "updater_error_log": "Error: {error}",
        "updater_error_dialog": "Could not prepare the update:\n{error}",
        "updater_downloaded": "Downloaded {done} of {total} MiB ({percent}%).",
        "updater_download_unknown": "Downloaded {done} MiB…",
        "updater_no_installer": "No Windows EXE installer was found in the latest release.",
        "updater_no_digest": "The GitHub release has no installer SHA-256 digest; download cancelled.",
        "updater_digest_mismatch": "The installer SHA-256 does not match the GitHub release.",
        "updater_windows_only": "This updater is for Windows only.",
    }
)

TEXT["pl"].update(
    {
        "ocr_no_text": "OCR nie znalazł tekstu na tym zdjęciu.",
        "statistics_group_invalid": "Wybierz grupowanie dzienne lub miesięczne.",
        "settings_save_failed": "Nie udało się zapisać ustawień: {error}",
        "settings_invalid": "Sprawdź język, motyw i styl ikon.",
        "settings_api_restore_failed": "Ustawienia nie zostały zapisane i nie udało się przywrócić poprzedniej konfiguracji API. Sprawdź dostępność portu i zapisz ponownie.",
        "api_bearer_required": "Wymagany jest token Bearer.",
        "api_key_invalid": "Klucz API jest nieprawidłowy lub unieważniony.",
        "api_key_expired": "Klucz API wygasł.",
        "api_rate_exceeded": "Przekroczono limit żądań. Spróbuj ponownie później.",
        "editor_rotation_range": "Kąt obrotu musi wynosić od −180 do 180 stopni.",
        "editor_resize_range": "Procent zmiany rozmiaru musi wynosić od 25 do 300.",
        "editor_adjustment_range": "Wartości ustawień obrazu muszą wynosić od 0 do 200.",
        "image_outside_folder": "Zdjęcie znajduje się poza wybranym folderem.",
        "splitter_unknown": "Nieznany separator paneli.",
        "ai_no_text": "Dostawca AI nie zwrócił rozpoznanego tekstu.",
        "startup_log_retry": "Ponowna próba zapisu dziennika uruchamiania po błędzie dostępu.",
        "updater_title": "Advanced Serial Vision — aktualizator",
        "updater_heading": "Oddzielny aktualizator wcześniejszych wersji Advanced Serial Vision",
        "updater_language": "Język interfejsu",
        "updater_system_language": "Automatycznie (język systemu)",
        "updater_ready": "Gotowy do sprawdzenia aktualizacji.",
        "updater_install": "Pobierz i uruchom instalator",
        "updater_close": "Zamknij",
        "updater_log": "Dziennik procesu",
        "updater_checking": "Sprawdzanie najnowszego wydania…",
        "updater_request": "Pobieranie informacji z GitHub Releases.",
        "updater_downloading": "Pobieranie wersji {version}…",
        "updater_source": "Źródło: {url}",
        "updater_verified": "Plik zweryfikowano. Otwieranie instalatora…",
        "updater_verified_path": "Zweryfikowano SHA-256: {path}",
        "updater_done": "Uruchomiono instalator. Potwierdź aktualizację w jego oknie; w razie potrzeby zamknie on starszy Serial Vision.",
        "updater_error_status": "Nie przeprowadzono aktualizacji.",
        "updater_error_log": "Błąd: {error}",
        "updater_error_dialog": "Nie udało się przygotować aktualizacji:\n{error}",
        "updater_downloaded": "Pobrano {done} z {total} MiB ({percent}%).",
        "updater_download_unknown": "Pobrano {done} MiB…",
        "updater_no_installer": "W najnowszym wydaniu nie znaleziono instalatora EXE dla Windows.",
        "updater_no_digest": "Wydanie GitHub nie zawiera sumy SHA-256 instalatora; anulowano pobieranie.",
        "updater_digest_mismatch": "Suma SHA-256 instalatora nie zgadza się z wydaniem GitHub.",
        "updater_windows_only": "Ten aktualizator jest przeznaczony wyłącznie dla Windows.",
    }
)

TEXT["uk"].update(
    {
        "gallery_loading": "Завантаження фото…",
        "gallery_failed": "Не вдалося завантажити фото: {error}",
        "statistics_loading": "Обчислення статистики…",
        "statistics_failed": "Не вдалося обчислити статистику: {error}",
    }
)
TEXT["en"].update(
    {
        "gallery_loading": "Loading photos…",
        "gallery_failed": "Could not load photos: {error}",
        "statistics_loading": "Calculating statistics…",
        "statistics_failed": "Could not calculate statistics: {error}",
    }
)
TEXT["pl"].update(
    {
        "gallery_loading": "Wczytywanie zdjęć…",
        "gallery_failed": "Nie udało się wczytać zdjęć: {error}",
        "statistics_loading": "Obliczanie statystyk…",
        "statistics_failed": "Nie udało się obliczyć statystyk: {error}",
    }
)
