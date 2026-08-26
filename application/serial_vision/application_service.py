from __future__ import annotations

import sqlite3
import keyring
from pathlib import Path

from serial_vision.database import Database
from serial_vision.i18n import system_locale
from serial_vision.ai_vision import AiVisionRecognizer


class SerialVisionService:
    """Application boundary used by Qt widgets for commands and read queries."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def image_directory(self) -> Path | None:
        value = self._database.setting("image_directory")
        return Path(value) if value and Path(value).is_dir() else None

    def save_settings(self, image_directory: Path, tesseract_binary: str) -> None:
        self._database.set_setting("image_directory", str(image_directory.resolve()))
        self._database.set_setting("tesseract_binary", tesseract_binary or "tesseract")

    def tesseract_binary(self) -> str:
        return self._database.setting("tesseract_binary", "tesseract")

    def locale(self) -> str:
        return self._database.setting("locale", system_locale()) if self._database.has_setting("locale") else system_locale()

    def save_locale(self, locale: str) -> None:
        self._database.set_setting("locale", locale)

    def ai_agents(self) -> list[sqlite3.Row]:
        return self._database.ai_agents()

    def save_ai_agent(self, name: str, provider: str, model: str, token: str) -> None:
        credential_id = f"serial-vision:{name}:{provider}:{model}"
        keyring.set_password("Serial Vision", credential_id, token)
        self._database.save_ai_agent(name, provider, model, credential_id)

    def delete_ai_agent(self, agent_id: str) -> None:
        agent = next((row for row in self.ai_agents() if row["id"] == agent_id), None)
        if agent is not None:
            keyring.delete_password("Serial Vision", agent["credential_id"])
        self._database.delete_ai_agent(agent_id)

    def recognize_ai(self, agent_id: str, image_path: Path) -> str:
        agent = next((row for row in self.ai_agents() if row["id"] == agent_id), None)
        if agent is None:
            raise RuntimeError("AI profile not found.")
        token = keyring.get_password("Serial Vision", agent["credential_id"])
        if not token:
            raise RuntimeError("AI profile key is unavailable in the Windows Credential Manager.")
        return AiVisionRecognizer().recognize(agent["provider"], agent["model"], token, image_path)

    def models(self) -> list[sqlite3.Row]:
        return self._database.models()

    def add_model(self, name: str, device_type: str, service: str) -> None:
        self._database.save_model(None, name, device_type, service)

    def delete_model(self, model_id: int) -> None:
        self._database.delete_model(model_id)

    def add_device(self, data: dict[str, object]) -> None:
        self._database.save_device(None, data)

    def update_device(self, device_id: int, data: dict[str, object]) -> None:
        self._database.save_device(device_id, data)

    def delete_device(self, device_id: int) -> None:
        self._database.delete_device(device_id)

    def devices(self, search: str = "", device_type: str = "", service: str = "", date_from: str = "", date_to: str = "", model_id: int | None = None, operation: str = "") -> list[sqlite3.Row]:
        return self._database.devices(search, device_type, service, date_from, date_to, model_id, operation)

    def export_devices(self, destination: Path, rows: list[sqlite3.Row]) -> None:
        self._database.export_csv(destination, rows)

    def statistics(self) -> list[sqlite3.Row]:
        return self._database.statistics()
