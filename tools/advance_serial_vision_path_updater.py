from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path
from queue import Empty, Queue
from typing import Callable
from tkinter import BOTH, DISABLED, END, NORMAL, RIGHT, X, Button, Label, StringVar, Tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText


REPOSITORY = "homeandriy/advanced_serial_vision"
USER_AGENT = "Advanced-Serial-Vision-Path-Updater"


class LegacyUpdater:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title("Advanced Serial Vision — оновлювач")
        self.root.minsize(680, 460)
        self.status = StringVar(value="Готово до перевірки оновлення.")
        self.progress = ttk.Progressbar(self.root, mode="determinate", maximum=100)
        self.log = ScrolledText(self.root, height=14, state=DISABLED, wrap="word")
        self.events: Queue[tuple[str, object]] = Queue()
        self.install_button = Button(self.root, text="Завантажити та запустити інсталятор", command=self.start_update)
        self.close_button = Button(self.root, text="Закрити", command=self.root.destroy)
        self._layout()
        self.root.after(100, self.process_events)

    def _layout(self) -> None:
        Label(self.root, text="Окремий оновлювач для попередніх версій Advanced Serial Vision", anchor="w").pack(fill=X, padx=16, pady=(16, 6))
        Label(self.root, textvariable=self.status, anchor="w", justify="left", wraplength=640).pack(fill=X, padx=16, pady=(0, 10))
        self.progress.pack(fill=X, padx=16, pady=(0, 10))
        Label(self.root, text="Журнал процесу", anchor="w").pack(fill=X, padx=16)
        self.log.pack(fill=BOTH, expand=True, padx=16, pady=(4, 12))
        self.close_button.pack(side=RIGHT, padx=(4, 16), pady=(0, 16))
        self.install_button.pack(side=RIGHT, padx=4, pady=(0, 16))

    def add_log(self, message: str) -> None:
        self.log.configure(state=NORMAL)
        self.log.insert(END, f"{message}\n")
        self.log.see(END)
        self.log.configure(state=DISABLED)

    def start_update(self) -> None:
        self.install_button.configure(state=DISABLED)
        self.progress.configure(value=0)
        self.status.set("Перевірка останнього релізу…")
        self.add_log("Запит до GitHub Releases.")
        threading.Thread(target=self.download_and_launch, daemon=True).start()

    def emit(self, event: str, value: object) -> None:
        self.events.put((event, value))

    def download_and_launch(self) -> None:
        try:
            release = latest_windows_release()
            self.emit("status", f"Завантаження v{release['version']}…")
            self.emit("log", f"Джерело: {release['url']}")
            installer = download_verified_installer(release, lambda done, total: self.emit("progress", (done, total)))
            self.emit("progress", (1, 1))
            self.emit("status", "Файл перевірено. Відкривається видимий інсталятор…")
            self.emit("log", f"SHA-256 перевірено: {installer}")
            subprocess.Popen([str(installer), "/CLOSEAPPLICATIONS", "/NORESTART"], close_fds=True)
            self.emit("done", "Інсталятор запущено. Підтвердіть оновлення у його вікні; він закриє старий Serial Vision за потреби.")
        except Exception as error:
            self.emit("error", str(error))

    def process_events(self) -> None:
        try:
            while True:
                event, value = self.events.get_nowait()
                if event == "status":
                    self.status.set(str(value))
                elif event == "log":
                    self.add_log(str(value))
                elif event == "progress":
                    done, total = value  # type: ignore[misc]
                    if total:
                        percent = min(100, int(done * 100 / total))
                        self.progress.configure(value=percent)
                        self.status.set(f"Завантажено {done / 1024 / 1024:.1f} з {total / 1024 / 1024:.1f} MiB ({percent}%).")
                    else:
                        self.progress.configure(value=min(99, int(float(self.progress["value"])) + 1))
                elif event == "done":
                    self.status.set(str(value))
                    self.add_log(str(value))
                    self.install_button.configure(state=DISABLED)
                    messagebox.showinfo("Оновлювач", str(value), parent=self.root)
                elif event == "error":
                    self.status.set("Оновлення не виконано.")
                    self.add_log(f"Помилка: {value}")
                    self.install_button.configure(state=NORMAL)
                    messagebox.showerror("Оновлювач", f"Не вдалося підготувати оновлення:\n{value}", parent=self.root)
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
        (item for item in payload.get("assets", []) if str(item.get("name", "")).startswith("SerialVision-Setup-") and str(item.get("name", "")).lower().endswith(".exe")),
        None,
    )
    if not asset:
        raise RuntimeError("У поточному релізі не знайдено Windows EXE-інсталятора.")
    digest = str(asset.get("digest", "")).removeprefix("sha256:")
    if not digest:
        raise RuntimeError("GitHub Release не містить SHA-256 для інсталятора; завантаження скасовано.")
    return {"version": str(payload.get("tag_name", "")).lstrip("v"), "url": str(asset["browser_download_url"]), "sha256": digest}


def download_verified_installer(release: dict[str, str], progress: Callable[[int, int | None], None]) -> Path:
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
        raise RuntimeError("SHA-256 інсталятора не збігається з даними GitHub Release.")
    return destination


if __name__ == "__main__":
    if os.name != "nt":
        raise SystemExit("This updater is for Windows only.")
    LegacyUpdater().root.mainloop()
