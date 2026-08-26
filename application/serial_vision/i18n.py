from __future__ import annotations

from PySide6.QtCore import QLocale


SUPPORTED_LOCALES = ("uk", "en", "pl")


def system_locale() -> str:
    candidate = QLocale.system().name().split("_", 1)[0].lower()
    return candidate if candidate in SUPPORTED_LOCALES else "uk"


def t(locale: str, key: str, **values: str) -> str:
    return TEXT[locale].get(key, TEXT["uk"][key]).format(**values)


_uk = {
    "app_name": "Serial Vision", "open": "Відкрити", "exit": "Вийти", "recognition": "Розпізнавання", "equipment": "Обладнання", "models": "Моделі", "statistics": "Статистика", "settings": "Налаштування", "help": "Довідка", "about": "Про програму", "images": "Зображення", "ocr": "OCR-розпізнавання", "barcodes": "Штрихкоди", "ai": "AI-розпізнавання", "ocr_language": "Мова OCR", "select_image": "Оберіть фото", "ocr_empty": "Результат OCR з’явиться тут.", "barcode_empty": "Результат штрихкодів з’явиться тут.", "ai_empty": "Додайте та оберіть AI-профіль у налаштуваннях.", "refresh": "Оновити", "rotate": "Повернути праворуч", "delete": "Видалити", "run_ocr": "Розпізнати OCR", "run_barcode": "Прочитати штрихкоди", "choose_folder": "Обрати папку", "open_folder": "Відкрити папку", "save": "Зберегти", "export": "Експорт CSV", "language": "Мова інтерфейсу", "image_folder": "Папка з фото", "ai_profiles": "AI-профілі", "profile_name": "Назва", "provider": "Постачальник", "model": "Модель", "api_key": "API-ключ", "add_profile": "Додати профіль", "remove_profile": "Видалити профіль", "no_profiles": "AI-профілі ще не налаштовані.", "developer": "Розробник: homeandriy", "version": "Версія {version}", "type": "Тип", "service": "Послуга", "all_types": "Усі типи", "all_services": "Усі послуги", "modem": "Модем", "tuner": "Тюнер", "internet": "Інтернет", "television": "Телебачення", "receipt": "Прийом", "issue": "Видача", "operation": "Операція", "contract": "Номер договору", "recognized_text": "Серійний номер / MAC / текст", "date_time": "Дата і час", "model_name": "Назва моделі", "search": "Пошук за текстом", "confirm": "Підтвердження", "error": "Помилка", "no_image": "Спершу виберіть зображення.", "folder_missing": "Вибрана папка не існує або недоступна.", "profile_saved": "AI-профіль збережено.", "profile_required": "Оберіть AI-профіль.", "restart_language": "Мову збережено. Вона застосовується після перезапуску.", "status_ready": "Готово", "barcodes_not_found": "Штрихкодів не знайдено.", "about_text": "Локальний облік обладнання та OCR.", "delete_image": "Видалити вибране фото? Запис обладнання залишиться.", "delete_device": "Видалити вибраний запис обладнання?", "delete_model": "Видалити вибрану модель?"}

_en = {"app_name": "Serial Vision", "recognition": "Recognition", "equipment": "Equipment", "models": "Models", "statistics": "Statistics", "settings": "Settings", "help": "Help", "about": "About", "images": "Images", "ocr": "OCR recognition", "barcodes": "Barcodes", "ai": "AI recognition", "ocr_language": "OCR language", "select_image": "Select an image", "ocr_empty": "OCR result will appear here.", "barcode_empty": "Barcode result will appear here.", "ai_empty": "Add and select an AI profile in Settings.", "refresh": "Refresh", "rotate": "Rotate right", "delete": "Delete", "run_ocr": "Run OCR", "run_barcode": "Read barcodes", "choose_folder": "Choose folder", "open_folder": "Open folder", "save": "Save", "export": "Export CSV", "language": "Interface language", "image_folder": "Image folder", "ai_profiles": "AI profiles", "profile_name": "Name", "provider": "Provider", "model": "Model", "api_key": "API key", "add_profile": "Add profile", "remove_profile": "Remove profile", "no_profiles": "No AI profiles configured.", "developer": "Developer: homeandriy", "version": "Version {version}", "type": "Type", "service": "Service", "all_types": "All types", "all_services": "All services", "modem": "Modem", "tuner": "Tuner", "internet": "Internet", "television": "Television", "receipt": "Receipt", "issue": "Issue", "operation": "Operation", "contract": "Contract number", "recognized_text": "Serial number / MAC / text", "date_time": "Date and time", "model_name": "Model name", "search": "Search text", "confirm": "Confirmation", "error": "Error", "no_image": "Select an image first.", "folder_missing": "The selected folder is unavailable.", "profile_saved": "AI profile saved.", "profile_required": "Select an AI profile.", "restart_language": "Language saved. It will apply after restart.", "status_ready": "Ready", "barcodes_not_found": "No barcodes found.", "about_text": "Local equipment records and OCR.", "delete_image": "Delete selected photo? Equipment records stay.", "delete_device": "Delete selected equipment record?", "delete_model": "Delete selected model?"}

_pl = {"app_name": "Serial Vision", "recognition": "Rozpoznawanie", "equipment": "Sprzęt", "models": "Modele", "statistics": "Statystyki", "settings": "Ustawienia", "help": "Pomoc", "about": "O programie", "images": "Obrazy", "ocr": "Rozpoznawanie OCR", "barcodes": "Kody kreskowe", "ai": "Rozpoznawanie AI", "ocr_language": "Język OCR", "select_image": "Wybierz obraz", "ocr_empty": "Wynik OCR pojawi się tutaj.", "barcode_empty": "Wynik kodów pojawi się tutaj.", "ai_empty": "Dodaj i wybierz profil AI w Ustawieniach.", "refresh": "Odśwież", "rotate": "Obróć w prawo", "delete": "Usuń", "run_ocr": "Uruchom OCR", "run_barcode": "Odczytaj kody", "choose_folder": "Wybierz folder", "open_folder": "Otwórz folder", "save": "Zapisz", "export": "Eksport CSV", "language": "Język interfejsu", "image_folder": "Folder obrazów", "ai_profiles": "Profile AI", "profile_name": "Nazwa", "provider": "Dostawca", "model": "Model", "api_key": "Klucz API", "add_profile": "Dodaj profil", "remove_profile": "Usuń profil", "no_profiles": "Brak profili AI.", "developer": "Programista: homeandriy", "version": "Wersja {version}", "type": "Typ", "service": "Usługa", "all_types": "Wszystkie typy", "all_services": "Wszystkie usługi", "modem": "Modem", "tuner": "Tuner", "internet": "Internet", "television": "Telewizja", "receipt": "Przyjęcie", "issue": "Wydanie", "operation": "Operacja", "contract": "Numer umowy", "recognized_text": "Numer seryjny / MAC / tekst", "date_time": "Data i czas", "model_name": "Nazwa modelu", "search": "Szukaj tekstu", "confirm": "Potwierdzenie", "error": "Błąd", "no_image": "Najpierw wybierz obraz.", "folder_missing": "Wybrany folder jest niedostępny.", "profile_saved": "Profil AI zapisano.", "profile_required": "Wybierz profil AI.", "restart_language": "Język zapisano. Zostanie zastosowany po restarcie.", "status_ready": "Gotowe", "barcodes_not_found": "Nie znaleziono kodów kreskowych.", "about_text": "Lokalna ewidencja sprzętu i OCR.", "delete_image": "Usunąć wybrane zdjęcie? Rekordy sprzętu pozostaną.", "delete_device": "Usunąć wybrany rekord sprzętu?", "delete_model": "Usunąć wybrany model?"}

TEXT = {"uk": _uk, "en": _en, "pl": _pl}
for _locale, _values in TEXT.items():
    _values.setdefault("open", {"en": "Open", "pl": "Otwórz"}.get(_locale, "Відкрити"))
    _values.setdefault("exit", {"en": "Exit", "pl": "Wyjdź"}.get(_locale, "Вийти"))
    _values.setdefault("copy", {"en": "Copy", "pl": "Kopiuj"}.get(_locale, "Копіювати"))
    _values.setdefault("add_to_database", {"en": "Add to database", "pl": "Dodaj do bazy"}.get(_locale, "Додати в БД"))
    _values.setdefault("add_raw_to_database", {"en": "Add unformatted to database", "pl": "Dodaj bez formatowania do bazy"}.get(_locale, "Додати в БД неформатовано"))
    _values.setdefault("new_equipment", {"en": "New equipment record", "pl": "Nowy wpis sprzętu"}.get(_locale, "Новий запис обладнання"))
    _values.setdefault("add_record", {"en": "Add record", "pl": "Dodaj wpis"}.get(_locale, "Додати запис"))
    _values.setdefault("edit", {"en": "Edit", "pl": "Edytuj"}.get(_locale, "Редагувати"))

_uk.update({"first_run": "Перший запуск", "license_text": "Підтвердіть згоду з умовами та оберіть папку з фото.", "accept_and_continue": "Прийняти та продовжити", "startup_log": "Відкрити лог запуску", "check_updates": "Перевірити оновлення", "update_not_configured": "Перевірка оновлень ще не налаштована."})

_en.update({"first_run": "First launch", "license_text": "Accept the terms and select the image folder.", "accept_and_continue": "Accept and continue", "startup_log": "Open startup log", "check_updates": "Check for updates", "update_not_configured": "Update checking is not configured yet."})
_pl.update({"first_run": "Pierwsze uruchomienie", "license_text": "Zaakceptuj warunki i wybierz folder obrazów.", "accept_and_continue": "Akceptuj i kontynuuj", "startup_log": "Otwórz dziennik uruchamiania", "check_updates": "Sprawdź aktualizacje", "update_not_configured": "Sprawdzanie aktualizacji nie jest jeszcze skonfigurowane."})

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

TEXT["uk"].update({"license_acceptance": "Я приймаю умови використання", "license_required": "Потрібно підтвердити згоду з умовами.", "source_image_missing": "Файл вихідного фото вже не існує або недоступний.", "total": "Разом"})

TEXT["en"].update({"license_acceptance": "I accept the terms of use", "license_required": "You must accept the terms.", "source_image_missing": "The linked photo no longer exists or is unavailable.", "total": "Total"})
TEXT["pl"].update({"license_acceptance": "Akceptuje warunki uzytkowania", "license_required": "Musisz zaakceptowac warunki.", "source_image_missing": "Plik zrodlowego zdjecia juz nie istnieje lub jest niedostepny.", "total": "Razem"})

TEXT["uk"].update({"contract_too_long": "Номер договору має містити до 20 символів.", "model_exists": "Модель з такою назвою, типом і послугою вже існує.", "model_in_use": "Не можна видалити модель, що використана у записах обладнання."})

TEXT["en"].update({"contract_too_long": "Contract number must not exceed 20 characters.", "model_exists": "A model with this name, type and service already exists.", "model_in_use": "A model linked to equipment records cannot be deleted."})
TEXT["pl"].update({"contract_too_long": "Numer umowy moze miec najwyzej 20 znakow.", "model_exists": "Model o tej nazwie, typie i usludze juz istnieje.", "model_in_use": "Nie mozna usunac modelu powiazanego z wpisami sprzetu."})

TEXT["uk"].update({"previous_page": "Попередня сторінка", "next_page": "Наступна сторінка"})
TEXT["en"].update({"previous_page": "Previous page", "next_page": "Next page"})
TEXT["pl"].update({"previous_page": "Poprzednia strona", "next_page": "Nastepna strona"})

TEXT["uk"]["open_source_image"] = "Відкрити вихідне фото"
TEXT["en"]["open_source_image"] = "Open source image"
TEXT["pl"]["open_source_image"] = "Otworz zdjecie zrodlowe"

TEXT["uk"].update({"menu_file": "Файл", "menu_edit": "Редагувати", "menu_view": "Вигляд", "help_contents": "Довідка", "help_text": "Оберіть фото, щоб автоматично запустити OCR і читання штрихкодів. Виділений результат можна скопіювати або додати до обліку через праву кнопку миші.", "select_text_to_copy": "Виділіть текст у полі результату, щоб скопіювати його.", "recognizing": "Виконується розпізнавання…", "interface_settings": "Інтерфейс", "folder_settings": "Папка зображень", "update_settings": "Оновлення", "save_interface": "Зберегти інтерфейс", "save_folder": "Зберегти папку", "save_updates": "Зберегти оновлення", "settings_saved": "Налаштування збережено."})
TEXT["en"].update({"menu_file": "File", "menu_edit": "Edit", "menu_view": "View", "help_contents": "Help", "help_text": "Select a photo to start OCR and barcode reading automatically. Right-click selected results to copy them or add them to equipment.", "select_text_to_copy": "Select text in a result field to copy it.", "recognizing": "Recognition in progress…", "interface_settings": "Interface", "folder_settings": "Image folder", "update_settings": "Updates", "save_interface": "Save interface", "save_folder": "Save folder", "save_updates": "Save updates", "settings_saved": "Settings saved."})
TEXT["pl"].update({"menu_file": "Plik", "menu_edit": "Edycja", "menu_view": "Widok", "help_contents": "Pomoc", "help_text": "Wybierz zdjęcie, aby automatycznie uruchomić OCR i odczyt kodów. Kliknij prawym przyciskiem zaznaczony wynik, aby go skopiować lub dodać do sprzętu.", "select_text_to_copy": "Zaznacz tekst w polu wyniku, aby go skopiować.", "recognizing": "Trwa rozpoznawanie…", "interface_settings": "Interfejs", "folder_settings": "Folder obrazów", "update_settings": "Aktualizacje", "save_interface": "Zapisz interfejs", "save_folder": "Zapisz folder", "save_updates": "Zapisz aktualizacje", "settings_saved": "Ustawienia zapisano."})

TEXT["uk"]["open_image"] = "Відкрити зображення"
TEXT["en"]["open_image"] = "Open image"
TEXT["pl"]["open_image"] = "Otwórz obraz"

TEXT["uk"].update({"automatic_update_unsupported": "Автоматичне оновлення доступне лише у Windows-інсталяторі.", "update_integrity_failed": "Не вдалося перевірити цілісність завантаженого оновлення.", "update_available_manual": "Доступна версія {version}. Встановіть її з опублікованих файлів релізу."})
TEXT["en"].update({"automatic_update_unsupported": "Automatic updates are available only in the Windows installer.", "update_integrity_failed": "The downloaded update could not be verified.", "update_available_manual": "Version {version} is available. Install it from the release assets."})
TEXT["pl"].update({"automatic_update_unsupported": "Automatyczne aktualizacje są dostępne tylko w instalatorze Windows.", "update_integrity_failed": "Nie można zweryfikować pobranej aktualizacji.", "update_available_manual": "Dostępna jest wersja {version}. Zainstaluj ją z plików wydania."})
