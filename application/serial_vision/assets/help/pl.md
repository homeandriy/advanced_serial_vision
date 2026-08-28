<!-- section: overview -->
## O programie Advanced Serial Vision

Advanced Serial Vision to lokalna aplikacja do ewidencji sprzętu i pracy ze zdjęciami etykiet fabrycznych. Pomaga odczytać numer seryjny, adres MAC, kod kreskowy lub inny tekst, sprawdzić wynik i zapisać uporządkowaną operację sprzętową. Rekordy i ustawienia pozostają w danych bieżącego użytkownika; codzienna praca nie wymaga Internetu.

Typowy proces to: wybór zdjęcia, lokalne rozpoznanie, ręczna korekta wartości, wybór modelu i zapis rekordu. Zapisane dane można odnaleźć filtrami, otworzyć powiązane zdjęcie, wyeksportować do CSV i uwzględnić w statystykach.

<!-- section: first-start -->
## Pierwsze uruchomienie i dane lokalne

Przy pierwszym uruchomieniu zaakceptuj warunki i wybierz główny folder ze zdjęciami. Program odczytuje obsługiwane pliki obrazów z niego i z podfolderów, ale nie przenosi ich samodzielnie. Wybierz folder dostępny dla bieżącego użytkownika Windows.

Folder zdjęć nie jest folderem instalacji programu. Lokalna baza, ustawienia i dziennik uruchomienia są przechowywane w katalogu danych użytkownika, więc aktualizacja nie powinna usuwać rekordów sprzętu. Gdy źródłowy folder lub plik zostanie przeniesiony, rekord pozostaje w bazie, lecz otwarcie zdjęcia może przestać działać.

<!-- section: navigation -->
## Nawigacja i bezpieczna praca

Rozpoznawanie służy do pracy z jednym wybranym zdjęciem, Sprzęt do rejestru i eksportu, Modele do słownika modeli, Statystyki do podsumowań, a Ustawienia do języka, wyglądu, folderu i opcjonalnych profili AI. Ważne polecenia są także w menu Plik, Widok i Pomoc.

Przyciski ze znakiem zapytania otwierają właściwy temat pomocy. Podpowiedzi opisują zwarte przyciski ikon. Usunięcie zdjęcia nie usuwa rekordu sprzętu. Usunięcie modelu użytego w rekordach jest blokowane, aby chronić historię. Zawsze przeczytaj potwierdzenie przed usunięciem.

<!-- section: images -->
## Zdjęcia: wybór i przygotowanie

Katalog obrazów jest rekursywny i stronicowany, dlatego może obsłużyć duże foldery. Wybierz kartę obrazu, aby zobaczyć podgląd. Lokalne OCR i odczyt kodów kreskowych uruchamiają się w tle po wyborze; poczekaj na wynik i dokładnie go sprawdź.

Używaj Obróć w prawo tylko dla właściwego pliku, ponieważ zmienia on zdjęcie źródłowe. Otwórz uruchamia systemowy podgląd, a Usuń działa tylko wewnątrz wybranego folderu głównego i wymaga potwierdzenia. Najlepszy wynik daje ostre zdjęcie etykiety wykonane prostopadle, bez odblasków i z marginesem wokół tekstu lub kodu.

<!-- section: ocr -->
## Lokalne rozpoznawanie OCR

Advanced Serial Vision używa RapidOCR lokalnie. Wybór zdjęcia lub uruchomienie OCR nie wysyła go do chmury. Wybierz język najlepiej odpowiadający etykiecie: English dla większości oznaczeń technicznych, Українська lub Polski dla tekstu pomocniczego. Język poprawia rozpoznawanie, lecz nie zastępuje kontroli człowieka.

Wynik OCR można edytować. Skopiuj go z menu kontekstowego lub Edycja i popraw niejednoznaczne znaki przed zapisem. Częste pomyłki to O/0, I/1, S/5 oraz B/8. Jeżeli tekstu nie znaleziono, użyj wyraźniejszego zdjęcia, zmień orientację lub język OCR.

<!-- section: barcode-ai -->
## Kody kreskowe i opcjonalne rozpoznawanie AI

Użyj Odczytaj kody, aby pobrać obsługiwany kod 1D lub 2D ze zdjęcia. Brak wyniku może oznaczać, że kod jest zbyt mały, uszkodzony, błyszczący lub nieobsługiwany. Wynik jest tylko do odczytu; skopiuj go tam, gdzie jest potrzebny.

Rozpoznawanie AI jest opcjonalne i nie uruchamia się automatycznie. Wymaga wybranego zdjęcia oraz profilu z dostawcą, modelem i kluczem API. Sekret jest przechowywany w systemowym magazynie poświadczeń, a nie w SQLite. Żądanie AI może przesłać przygotowany obraz do wybranego dostawcy, więc używaj go tylko zgodnie z zasadami prywatności.

<!-- section: equipment -->
## Rejestracja sprzętu

Otwórz Sprzęt i wybierz Dodaj wpis. Wprowadź datę i czas, opcjonalny numer umowy, typ operacji, sprawdzony numer seryjny/MAC/tekst, model, typ urządzenia i usługę. Główny tekst jest wymagany, a numer umowy może mieć maksymalnie dwadzieścia znaków.

Przyjęcie i Wydanie są kierunkami operacji. Dostępne typy to Modem i Tuner, a usługi to Internet i Telewizja. Etykiety zależą od języka interfejsu, lecz w bazie są stałe kody. Czas jest wprowadzany i wyświetlany dla Europe/Kyiv, a zapisywany w UTC. Rekord przechowuje odnośnik do zdjęcia, nie jego kopię.

Kliknij dwukrotnie wiersz albo użyj Edytuj, aby poprawić rekord. Usunięcie rekordu jest nieodwracalne dla lokalnej bazy, dlatego przed potwierdzeniem sprawdź numer, datę i model.

W formularzu rekordu pod polem numeru seryjnego/MAC są przyciski Uzyskaj kod QR i Uzyskaj kod kreskowy. Tworzą kod tylko z bieżącego tekstu, otwierają podgląd i pozwalają zapisać PNG. Utworzenie kodu nie zapisuje ani nie zmienia rekordu sprzętu.

<!-- section: search-export -->
## Wyszukiwanie, filtry i eksport CSV

Filtry Sprzętu obejmują zakres dat, model, operację, typ urządzenia, usługę i fragment tekstu. Łącz je, a następnie wybierz Odśwież. Możesz na przykład znaleźć wszystkie wydania modemów Internetu w miesiącu albo fragment numeru seryjnego.

Tabela jest stronicowana, ale Eksport CSV obejmuje wszystkie rekordy zgodne z aktywnymi filtrami, nie tylko bieżącą stronę. Sprawdź wszystkie filtry przed eksportem. Wybierz czytelną nazwę pliku i zachowaj oryginalny eksport przed edycją w arkuszu. CSV używa Windows-1251 dla dobrej zgodności z Microsoft Excel w środowisku ukraińskim.

<!-- section: models -->
## Słownik modeli

Modele to kontrolowana lista typowego sprzętu. Model zawiera nazwę, typ urządzenia i usługę. Utwórz go raz i wybieraj przy rejestracji, aby zachować spójność eksportów i statystyk. Ta sama kombinacja nazwy, typu i usługi nie może wystąpić dwa razy.

Tabelę można sortować po nazwie i liczbie użyć. Liczba użyć oznacza liczbę powiązanych rekordów historycznych, a nie bieżący stan magazynu. Modelu powiązanego z rekordami nie można usunąć; dla nowego wariantu utwórz nowy model.

<!-- section: statistics -->
## Statystyki i wykresy

Statystyki grupują zapisane operacje według dnia albo miesiąca. Tabela pokazuje osobno Przyjęcia, Wydania i ich sumę. Wykresy podsumowują operacje, usługi oraz do dziesięciu najczęściej rejestrowanych modeli.

Wartości wykresów są liczbą rekordów, a nie aktualnym stanem magazynu. Aby sprawdzić pojedyncze urządzenie, wróć do Sprzętu i wyszukaj szczegółowy dziennik. Przy niepełnym podsumowaniu sprawdź zapisane daty, modele, kierunki operacji, typy i usługi.

<!-- section: settings -->
## Ustawienia interfejsu i wyglądu

W ustawieniach interfejsu wybierz ukraiński, angielski albo polski, zapisz wybór i uruchom program ponownie. Zmiana języka wpływa tylko na etykiety, nie na kody ani rekordy.

Zmieniaj folder zdjęć świadomie. Wygląd oferuje motyw systemowy, jasny i ciemny oraz style ikon: systemowy, nowoczesny, klasyczny, Windows 98 i Ubuntu 22. Zmieniają one prezentację, a nie dane. Tutaj zarządzasz też profilami AI; nigdy nie udostępniaj klucza API na zrzucie ekranu, w wiadomości ani w CSV.

<!-- section: updates-diagnostics -->
## Aktualizacje, dziennik i rozwiązywanie problemów

Pomoc zawiera Sprawdź aktualizacje i Otwórz dziennik uruchomienia. Oficjalne repozytorium jest sprawdzane w tle około minuty po uruchomieniu oraz na żądanie. W Windows dostępny instalator jest pobierany do katalogu tymczasowego, weryfikowany SHA-256 i uruchamiany po zamknięciu programu. Baza użytkownika nie jest częścią instalatora.

W Linux aktualizacja jest ręczna, ponieważ instalacja DEB może wymagać praw systemowych. Korzystaj wyłącznie z oficjalnych zasobów GitHub Release. Zgłoszenie problemu powinno zawierać wersję programu, kroki odtworzenia i bezpieczny fragment dziennika bez kluczy API i danych osobowych.

<!-- section: privacy -->
## Prywatność, kopie zapasowe i codzienna lista

RapidOCR, kody kreskowe, ewidencja sprzętu i ustawienia działają lokalnie. Sieć jest używana tylko przy wyraźnie zleconym AI lub sprawdzaniu aktualizacji. Przed użyciem AI upewnij się, że zdjęcie może opuścić urządzenie.

Twórz kopie katalogu danych programu i przechowuj oryginalne zdjęcia w bezpiecznym miejscu. CSV jest raportem, nie pełną kopią zapasową. Codziennie: wybierz właściwy folder, wyraźne zdjęcie, sprawdź wynik, wybierz model i operację, zapisz, wyszukaj rekord w razie potrzeby i sprawdź filtry przed eksportem.


<!-- section: integrations -->
## Integracje

Włącz lokalne API w Ustawieniach, utwórz klucz Bearer na karcie Integracje API i skopiuj go tylko raz. Użyj Authorization: Bearer sv_... w BAS lub Postman. Przykład: GET http://127.0.0.1:4556/api/v1/equipment. Swagger: http://127.0.0.1:4556/api/v1/docs.

Odpowiedzi sprzętu zwracają tylko `source_image_name`, nigdy lokalną ścieżkę pliku. Najpierw wywołaj `GET /api/v1/image/check/{record_id}`. `record_id` to `id` rekordu sprzętu, a nie `device_model_id`. Gdy odpowiedź zawiera `available: true`, wyślij `POST /api/v1/image/get` z `{ "record_id": 123 }`. Odpowiedź przesyła bajty obrazu, a oryginalna nazwa pliku z rozszerzeniem jest w standardowym nagłówku HTTP `Content-Disposition`.

Aby pobrać kod dla istniejącego rekordu sprzętu przez API, wyślij `POST /api/v1/code/get` z JSON `{ "record_id": 123, "type": "qrcode" }` lub `{ "record_id": 123, "type": "barcode" }`. `record_id` to `id` rekordu sprzętu, a nie `device_model_id`. Odpowiedzią jest strumień PNG: `barcode` używa Code 128, a nazwa, np. `qrcode_AABBCCDDEEFF_14_30_27_08_2026.png` lub `barcode_AABBCCDDEEFF_14_30_27_08_2026.png`, jest przekazywana w `Content-Disposition`. Kod jest generowany z `recognized_text` i nie jest osobno zapisywany w bazie.
