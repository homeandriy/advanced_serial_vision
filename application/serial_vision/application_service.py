from __future__ import annotations

import hashlib
import secrets
import sqlite3
from collections import defaultdict
import keyring
from datetime import UTC, datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from serial_vision.code_images import generated_code_filename, generate_code_png
from serial_vision.database import Database
from serial_vision.i18n import system_locale
from serial_vision.model_import import read_models_xlsx
from serial_vision.ai_vision import AiVisionRecognizer


class SerialVisionService:
    """Application boundary used by Qt widgets for commands and read queries."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def image_directory(self) -> Path | None:
        value = self._database.setting("image_directory")
        return Path(value) if value and Path(value).is_dir() else None

    def save_settings(self, image_directory: Path) -> None:
        if not image_directory.is_dir():
            raise ValueError("image_directory")
        self._database.set_setting("image_directory", str(image_directory.resolve()))

    def update_repository(self) -> str:
        return "homeandriy/serial_number_pythom"

    def theme(self) -> str:
        return self._database.setting("theme", "system")

    def icon_style(self) -> str:
        return self._database.setting("icon_style", "system")

    def save_appearance(self, theme: str, icon_style: str) -> None:
        self._database.set_setting("theme", theme)
        self._database.set_setting("icon_style", icon_style)

    def api_enabled(self) -> bool:
        return self._database.setting("api_enabled", "no") == "yes"

    def api_port(self) -> int:
        try: return int(self._database.setting("api_port", "4556"))
        except ValueError: return 4556

    def save_api_settings(self, enabled: bool, port: int) -> None:
        if not 1024 <= port <= 65535: raise ValueError("api_port_invalid")
        self._database.set_setting("api_enabled", "yes" if enabled else "no")
        self._database.set_setting("api_port", str(port))

    def issue_api_key(self, name: str, note: str, expires_at: str | None, min_interval_ms: int) -> str:
        if not name.strip(): raise ValueError("api_key_name_required")
        if min_interval_ms not in (200, 500, 1000, 2000): raise ValueError("api_rate_invalid")
        token = "sv_" + secrets.token_urlsafe(32)
        self._database.create_api_key(name.strip(), note.strip(), hashlib.sha256(token.encode()).hexdigest(), token[:12], expires_at, min_interval_ms)
        return token

    def api_keys(self) -> list[sqlite3.Row]: return self._database.api_keys()
    def revoke_api_key(self, key_id: str) -> None: self._database.revoke_api_key(key_id)
    def api_audit(self) -> list[sqlite3.Row]: return self._database.api_audit()

    def setup_required(self) -> bool:
        return self._database.setting("license_accepted") != "yes" or self.image_directory() is None

    def complete_setup(self, image_directory: Path) -> None:
        if not image_directory.is_dir():
            raise ValueError("The selected image folder is unavailable.")
        self.save_settings(image_directory)
        self._database.set_setting("license_accepted", "yes")

    def register_launch(self) -> int:
        return self._database.register_launch()

    def startup_log_path(self) -> Path:
        return self._database.path.parent / "startup.log"

    def log_startup(self, message: str) -> OSError | None:
        try:
            with self.startup_log_path().open("a", encoding="utf-8") as log:
                log.write(f"{datetime.now(UTC).isoformat()} {message}\n")
        except OSError as error:
            return error
        return None

    def locale(self) -> str:
        return self._database.setting("locale", system_locale()) if self._database.has_setting("locale") else system_locale()

    def save_locale(self, locale: str) -> None:
        self._database.set_setting("locale", locale)

    @staticmethod
    def display_time(value: str) -> str:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(ZoneInfo("Europe/Kyiv")).strftime("%d.%m.%Y %H:%M")

    def ai_agents(self) -> list[sqlite3.Row]:
        return self._database.ai_agents()

    def save_ai_agent(self, name: str, provider: str, model: str, token: str) -> None:
        credential_id = f"serial-vision:{name}:{provider}:{model}"
        keyring.set_password("Serial Vision", credential_id, token)
        self._database.save_ai_agent(name, provider, model, credential_id)

    def update_ai_agent(self, agent_id: str, name: str, provider: str, model: str, token: str) -> None:
        agent = next((row for row in self.ai_agents() if row["id"] == agent_id), None)
        if agent is None:
            raise ValueError("ai_profile_missing")
        credential_id = f"serial-vision:{name}:{provider}:{model}"
        secret = token or keyring.get_password("Serial Vision", agent["credential_id"])
        if not secret:
            raise ValueError("profile_key_required")
        keyring.set_password("Serial Vision", credential_id, secret)
        self._database.save_ai_agent(name, provider, model, credential_id, agent_id)
        if credential_id != agent["credential_id"]:
            try:
                keyring.delete_password("Serial Vision", agent["credential_id"])
            except keyring.errors.PasswordDeleteError:
                pass

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

    def popular_models(self) -> list[sqlite3.Row]:
        return self._database.popular_models()

    def add_model(self, name: str, device_type: str, service: str) -> None:
        try:
            self._database.save_model(None, name, device_type, service)
        except sqlite3.IntegrityError as error:
            raise ValueError("model_exists") from error

    def update_model(self, model_id: int, name: str, device_type: str, service: str) -> None:
        try:
            self._database.save_model(model_id, name, device_type, service)
        except sqlite3.IntegrityError as error:
            raise ValueError("model_exists") from error

    def import_models_xlsx(self, path: Path) -> dict[str, object]:
        imported = read_models_xlsx(path)
        existing = {(str(row["name"]).casefold(), str(row["device_type"]), str(row["service"])) for row in self.models()}
        added = duplicates = 0
        for model in imported.models:
            key = (model.name.casefold(), model.device_type, model.service)
            if key in existing:
                duplicates += 1
                continue
            self.add_model(model.name, model.device_type, model.service)
            existing.add(key)
            added += 1
        return {"added": added, "duplicates": duplicates, "invalid_rows": imported.errors}

    def delete_model(self, model_id: int) -> None:
        try:
            self._database.delete_model(model_id)
        except sqlite3.IntegrityError as error:
            raise ValueError("model_in_use") from error

    def add_device(self, data: dict[str, object]) -> None:
        self._validate_device_data(data)
        self._database.save_device(None, self._utc_device_data(data))

    def update_device(self, device_id: int, data: dict[str, object]) -> None:
        self._validate_device_data(data)
        self._database.save_device(device_id, self._utc_device_data(data))

    @staticmethod
    def _validate_device_data(data: dict[str, object]) -> None:
        if len(str(data.get("contract_number", "")).strip()) > 20:
            raise ValueError("contract_too_long")

    @staticmethod
    def _utc_device_data(data: dict[str, object]) -> dict[str, object]:
        copy = dict(data)
        value = datetime.fromisoformat(str(copy["registered_at"]))
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo("Europe/Kyiv"))
        copy["registered_at"] = value.astimezone(UTC).isoformat()
        return copy

    def source_image_path(self, device_id: int) -> Path | None:
        value = self._database.source_image_path(device_id)
        return Path(value) if value else None

    def generate_code_png(self, value: str, code_type: str) -> bytes:
        return generate_code_png(value, code_type)

    def generated_code_filename(self, value: str, code_type: str) -> str:
        return generated_code_filename(value, code_type)

    def device_recognized_text(self, device_id: int) -> str | None:
        return self._database.device_recognized_text(device_id)

    @staticmethod
    def save_generated_code(destination: Path, image_data: bytes) -> None:
        destination.write_bytes(image_data)

    def delete_device(self, device_id: int) -> None:
        self._database.delete_device(device_id)

    def devices(self, search: str = "", device_type: str = "", service: str = "", date_from: str = "", date_to: str = "", model_id: int | None = None, operation: str = "", page: int = 1) -> tuple[list[sqlite3.Row], dict[str, int] | None]:
        return self._database.devices(search, device_type, service, date_from, date_to, model_id, operation, page)

    def all_filtered_devices(self, search: str = "", device_type: str = "", service: str = "", date_from: str = "", date_to: str = "", model_id: int | None = None, operation: str = "") -> list[sqlite3.Row]:
        rows, _ = self._database.devices(search, device_type, service, date_from, date_to, model_id, operation, 1, 10_000_000)
        return rows

    def export_devices(self, destination: Path, rows: list[sqlite3.Row]) -> None:
        self._database.export_csv(destination, rows)

    def statistics_summary(self, group_by: str = "month") -> dict[str, object]:
        operations: dict[str, dict[str, int]] = defaultdict(lambda: {"receipt": 0, "issue": 0})
        services: dict[str, int] = defaultdict(int)
        models: dict[str, int] = defaultdict(int)
        for row in self._database.statistics_rows():
            value = datetime.fromisoformat(row["registered_at"])
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            local = value.astimezone(ZoneInfo("Europe/Kyiv"))
            period = local.strftime("%Y-%m-%d" if group_by == "day" else "%Y-%m")
            operations[period][row["operation_type"]] += 1
            services[row["service"]] += 1
            models[row["model_name"]] += 1
        return {"operations": dict(sorted(operations.items())), "services": dict(sorted(services.items())), "models": dict(sorted(models.items(), key=lambda item: (-item[1], item[0])))}

    def statistics(self) -> list[sqlite3.Row]:
        return self._database.statistics()
