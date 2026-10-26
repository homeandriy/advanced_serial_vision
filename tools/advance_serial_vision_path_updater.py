from __future__ import annotations

import hashlib
import json
import locale
import os
import subprocess
import tempfile
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path
from queue import Empty, Queue
from tkinter import (
    BOTH,
    DISABLED,
    END,
    NORMAL,
    RIGHT,
    Button,
    Label,
    StringVar,
    Tk,
    X,
    messagebox,
    ttk,
)
from tkinter.scrolledtext import ScrolledText

REPOSITORY = "homeandriy/advanced_serial_vision"
USER_AGENT = "Advanced-Serial-Vision-Path-Updater"

# Generated from updater_* keys in serial_vision.i18n.TEXT.
# Regenerate with make updater-translations; edit the central catalog only.
# Kept in this script so it can recover an installation without app dependencies.
# test_localization.py checks that this catalog matches the application catalog.
UPDATER_TEXT = {
    "uk": {
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
        "updater_done": "Інсталятор запущено. Підтвердіть оновлення у його вікні; він закриє "
        "старий Serial Vision за потреби.",
        "updater_error_status": "Оновлення не виконано.",
        "updater_error_log": "Помилка: {error}",
        "updater_error_dialog": "Не вдалося підготувати оновлення:\n{error}",
        "updater_downloaded": "Завантажено {done} з {total} MiB ({percent}%).",
        "updater_download_unknown": "Завантажено {done} MiB…",
        "updater_no_installer": "У поточному релізі не знайдено Windows EXE-інсталятора.",
        "updater_no_digest": "GitHub Release не містить SHA-256 для інсталятора; завантаження "
        "скасовано.",
        "updater_digest_mismatch": "SHA-256 інсталятора не збігається з даними GitHub Release.",
        "updater_windows_only": "Цей оновлювач призначений лише для Windows.",
    },
    "en": {
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
        "updater_done": "Installer started. Confirm the update in its window; it will close the "
        "old Serial Vision if needed.",
        "updater_error_status": "Update was not completed.",
        "updater_error_log": "Error: {error}",
        "updater_error_dialog": "Could not prepare the update:\n{error}",
        "updater_downloaded": "Downloaded {done} of {total} MiB ({percent}%).",
        "updater_download_unknown": "Downloaded {done} MiB…",
        "updater_no_installer": "No Windows EXE installer was found in the latest release.",
        "updater_no_digest": "The GitHub release has no installer SHA-256 digest; download "
        "cancelled.",
        "updater_digest_mismatch": "The installer SHA-256 does not match the GitHub release.",
        "updater_windows_only": "This updater is for Windows only.",
    },
    "pl": {
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
        "updater_done": "Uruchomiono instalator. Potwierdź aktualizację w jego oknie; w razie "
        "potrzeby zamknie on starszy Serial Vision.",
        "updater_error_status": "Nie przeprowadzono aktualizacji.",
        "updater_error_log": "Błąd: {error}",
        "updater_error_dialog": "Nie udało się przygotować aktualizacji:\n{error}",
        "updater_downloaded": "Pobrano {done} z {total} MiB ({percent}%).",
        "updater_download_unknown": "Pobrano {done} MiB…",
        "updater_no_installer": "W najnowszym wydaniu nie znaleziono instalatora EXE dla Windows.",
        "updater_no_digest": "Wydanie GitHub nie zawiera sumy SHA-256 instalatora; anulowano "
        "pobieranie.",
        "updater_digest_mismatch": "Suma SHA-256 instalatora nie zgadza się z wydaniem GitHub.",
        "updater_windows_only": "Ten aktualizator jest przeznaczony wyłącznie dla Windows.",
    },
}
LANGUAGES = ("auto", "uk", "en", "pl")
LANGUAGE_NAMES = ("Українська", "English", "Polski")


def system_language() -> str:
    candidate = ""
    if os.name == "nt":
        try:
            import ctypes

            language_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            candidate = locale.windows_locale.get(language_id, "")
        except (AttributeError, OSError):
            pass
    if not candidate:
        try:
            candidate = locale.getlocale()[0] or ""
        except (ValueError, TypeError):
            candidate = ""
    language = candidate.replace("-", "_").split("_", 1)[0].lower()
    return language if language in UPDATER_TEXT else "uk"


def translate(language: str, key: str, **values: object) -> str:
    catalog = UPDATER_TEXT.get(language, UPDATER_TEXT["uk"])
    return catalog[key].format(**values)


class LegacyUpdater:
    def __init__(self) -> None:
        self.root = Tk()
        self.locale = system_language()
        self.root.minsize(680, 460)
        self.status = StringVar()
        self._status = ("updater_ready", {})
        self._log_entries: list[tuple[str, dict[str, object]]] = []
        self.progress = ttk.Progressbar(self.root, mode="determinate", maximum=100)
        self.log = ScrolledText(self.root, height=14, state=DISABLED, wrap="word")
        self.events: Queue[tuple[str, object]] = Queue()
        self.install_button = Button(self.root, command=self.start_update)
        self.close_button = Button(self.root, command=self.root.destroy)
        self._layout()
        self.apply_language()
        self.root.after(100, self.process_events)

    def tr(self, key: str, **values: object) -> str:
        # Error values can be translation keys or external OS/network details.
        if "error" in values and str(values["error"]) in UPDATER_TEXT[self.locale]:
            values["error"] = translate(self.locale, str(values["error"]))
        return translate(self.locale, key, **values)

    def _layout(self) -> None:
        self.heading = Label(self.root, anchor="w", justify="left", wraplength=640)
        self.heading.pack(fill=X, padx=16, pady=(16, 6))
        language_bar = ttk.Frame(self.root)
        language_bar.pack(fill=X, padx=16, pady=(0, 10))
        self.language_label = ttk.Label(language_bar)
        self.language_label.pack(side="left", padx=(0, 8))
        self.language_choice = ttk.Combobox(
            language_bar,
            state="readonly",
            width=32,
            values=(self.tr("updater_system_language"), *LANGUAGE_NAMES),
        )
        self.language_choice.pack(side="left", fill=X, expand=True)
        self.language_choice.current(0)
        self.language_choice.bind("<<ComboboxSelected>>", self.change_language)
        Label(self.root, textvariable=self.status, anchor="w", justify="left", wraplength=640).pack(
            fill=X, padx=16, pady=(0, 10)
        )
        self.progress.pack(fill=X, padx=16, pady=(0, 10))
        self.log_label = Label(self.root, anchor="w")
        self.log_label.pack(fill=X, padx=16)
        self.log.pack(fill=BOTH, expand=True, padx=16, pady=(4, 12))
        self.close_button.pack(side=RIGHT, padx=(4, 16), pady=(0, 16))
        self.install_button.pack(side=RIGHT, padx=4, pady=(0, 16))

    def change_language(self, _event=None) -> None:
        selected = LANGUAGES[max(0, self.language_choice.current())]
        self.locale = system_language() if selected == "auto" else selected
        self.apply_language()

    def apply_language(self) -> None:
        selected = max(0, self.language_choice.current())
        self.root.title(self.tr("updater_title"))
        self.heading.configure(text=self.tr("updater_heading"))
        self.language_label.configure(text=self.tr("updater_language"))
        self.language_choice.configure(values=(self.tr("updater_system_language"), *LANGUAGE_NAMES))
        self.language_choice.current(selected)
        self.log_label.configure(text=self.tr("updater_log"))
        self.install_button.configure(text=self.tr("updater_install"))
        self.close_button.configure(text=self.tr("updater_close"))
        self.status.set(self.tr(self._status[0], **self._status[1]))
        self.render_log()

    def set_status(self, key: str, **values: object) -> None:
        self._status = (key, values)
        self.status.set(self.tr(key, **values))

    def add_log(self, key: str, **values: object) -> None:
        self._log_entries.append((key, values))
        self.render_log()

    def render_log(self) -> None:
        self.log.configure(state=NORMAL)
        self.log.delete("1.0", END)
        for key, values in self._log_entries:
            self.log.insert(END, self.tr(key, **values) + "\n")
        self.log.see(END)
        self.log.configure(state=DISABLED)

    def start_update(self) -> None:
        self.install_button.configure(state=DISABLED)
        self.progress.configure(value=0)
        self.set_status("updater_checking")
        self.add_log("updater_request")
        threading.Thread(target=self.download_and_launch, daemon=True).start()

    def emit(self, event: str, value: object) -> None:
        self.events.put((event, value))

    def download_and_launch(self) -> None:
        try:
            release = latest_windows_release()
            self.emit("status", ("updater_downloading", {"version": release["version"]}))
            self.emit("log", ("updater_source", {"url": release["url"]}))
            installer = download_verified_installer(
                release, lambda done, total: self.emit("progress", (done, total))
            )
            self.emit("verified", str(installer))
            subprocess.Popen([str(installer), "/CLOSEAPPLICATIONS", "/NORESTART"], close_fds=True)
            self.emit("done", None)
        except Exception as error:
            self.emit("error", str(error))

    def process_events(self) -> None:
        try:
            while True:
                event, value = self.events.get_nowait()
                if event in {"status", "log"}:
                    key, values = value
                    if event == "status":
                        self.set_status(key, **values)
                    else:
                        self.add_log(key, **values)
                elif event == "progress":
                    done, total = value
                    if total:
                        percent = min(100, int(done * 100 / total))
                        self.progress.configure(value=percent)
                        self.set_status(
                            "updater_downloaded",
                            done=f"{done / 1024 / 1024:.1f}",
                            total=f"{total / 1024 / 1024:.1f}",
                            percent=percent,
                        )
                    else:
                        self.progress.configure(
                            value=min(99, int(float(self.progress["value"])) + 1)
                        )
                        self.set_status(
                            "updater_download_unknown", done=f"{done / 1024 / 1024:.1f}"
                        )
                elif event == "verified":
                    self.progress.configure(value=100)
                    self.set_status("updater_verified")
                    self.add_log("updater_verified_path", path=value)
                elif event == "done":
                    self.set_status("updater_done")
                    self.add_log("updater_done")
                    self.install_button.configure(state=DISABLED)
                    messagebox.showinfo(
                        self.tr("updater_title"), self.tr("updater_done"), parent=self.root
                    )
                elif event == "error":
                    self.set_status("updater_error_status")
                    self.add_log("updater_error_log", error=value)
                    self.install_button.configure(state=NORMAL)
                    messagebox.showerror(
                        self.tr("updater_title"),
                        self.tr("updater_error_dialog", error=value),
                        parent=self.root,
                    )
        except Empty:
            pass
        self.root.after(100, self.process_events)


def latest_windows_release() -> dict[str, str]:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORY}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    asset = next(
        (
            item
            for item in payload.get("assets", [])
            if str(item.get("name", "")).startswith("SerialVision-Setup-")
            and str(item.get("name", "")).lower().endswith(".exe")
        ),
        None,
    )
    if not asset:
        raise RuntimeError("updater_no_installer")
    digest = str(asset.get("digest", "")).removeprefix("sha256:")
    if not digest:
        raise RuntimeError("updater_no_digest")
    return {
        "version": str(payload.get("tag_name", "")).lstrip("v"),
        "url": str(asset["browser_download_url"]),
        "sha256": digest,
    }


def download_verified_installer(
    release: dict[str, str], progress: Callable[[int, int | None], None]
) -> Path:
    directory = Path(tempfile.gettempdir()) / "advanced-serial-vision-path-updater"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / Path(release["url"].split("?", 1)[0]).name
    digest = hashlib.sha256()
    request = urllib.request.Request(release["url"], headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as target:
        value = response.headers.get("Content-Length")
        total = int(value) if value and value.isdigit() else None
        downloaded = 0
        while chunk := response.read(1024 * 1024):
            target.write(chunk)
            digest.update(chunk)
            downloaded += len(chunk)
            progress(downloaded, total)
    if digest.hexdigest().lower() != release["sha256"].lower():
        destination.unlink(missing_ok=True)
        raise RuntimeError("updater_digest_mismatch")
    return destination


if __name__ == "__main__":
    if os.name != "nt":
        raise SystemExit(translate(system_language(), "updater_windows_only"))
    LegacyUpdater().root.mainloop()
