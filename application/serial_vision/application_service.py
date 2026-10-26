from __future__ import annotations

import hashlib
import secrets
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import keyring

from serial_vision.ai_vision import AiVisionRecognizer
from serial_vision.code_images import generate_code_png, generated_code_filename
from serial_vision.contracts import ImportSummary, StatisticsSummary
from serial_vision.database import Database
from serial_vision.i18n import SUPPORTED_LOCALES, system_locale
from serial_vision.model_import import read_models_xlsx
from serial_vision.recognition_strategies import RecognitionOptions
from serial_vision.settings import SettingsRecoveryError, SettingsSaveError, SettingsValues


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

    def save_all_settings(
        self,
        settings: SettingsValues,
        reconfigure_api: Callable[[bool, int], None] | None = None,
    ) -> None:
        """Validate and persist one settings snapshot, compensating runtime failures."""
        try:
            port = int(settings.api_port)
        except ValueError as error:
            raise ValueError("api_port_invalid") from error
        if not 1024 <= port <= 65535:
            raise ValueError("api_port_invalid")
        if (
            settings.locale not in SUPPORTED_LOCALES
            or settings.theme not in ("system", "light", "dark")
            or settings.icon_style not in ("system", "modern", "classic", "windows98", "ubuntu22")
        ):
            raise ValueError("settings_invalid")
        directory = settings.image_directory
        previous_directory = self._database.setting("image_directory")
        if not directory:
            # A missing/unset picker must not discard a stored source-folder reference.
            directory = previous_directory
        elif directory != previous_directory:
            if not Path(directory).is_dir():
                raise ValueError("folder_missing")
            directory = str(Path(directory).resolve())
        previous_api = (self.api_enabled(), self.api_port())
        current_api = (settings.api_enabled, port)
        values = {
            "image_directory": directory,
            "theme": settings.theme,
            "icon_style": settings.icon_style,
            "recognition_rotate": "yes" if settings.rotate else "no",
            "recognition_enhance": "yes" if settings.enhance else "no",
            "api_enabled": "yes" if settings.api_enabled else "no",
            "api_port": str(port),
        }
        if settings.locale != self.locale():
            values["locale"] = settings.locale
        runtime_attempted = False

        def apply_runtime() -> None:
            nonlocal runtime_attempted
            if reconfigure_api is not None and current_api != previous_api:
                runtime_attempted = True
                reconfigure_api(*current_api)

        try:
            self._database.set_settings(values, apply_runtime)
        except Exception as error:
            if runtime_attempted and reconfigure_api is not None:
                try:
                    reconfigure_api(*previous_api)
                except Exception as recovery:
                    raise SettingsRecoveryError(error, recovery) from error
            if isinstance(error, (OSError, ValueError)):
                raise
            raise SettingsSaveError(str(error)) from error

    def update_repository(self) -> str:
        return "homeandriy/advanced_serial_vision"

    def recognition_options(self) -> RecognitionOptions:
        return RecognitionOptions(
            rotate=self._database.setting("recognition_rotate", "yes") == "yes",
            enhance=self._database.setting("recognition_enhance", "yes") == "yes",
        )

    def save_recognition_options(self, options: RecognitionOptions) -> None:
        self._database.set_setting("recognition_rotate", "yes" if options.rotate else "no")
        self._database.set_setting("recognition_enhance", "yes" if options.enhance else "no")

    def splitter_state(self, name: str) -> bytes | None:
        if name not in {"recognition_horizontal", "recognition_vertical"}:
            raise ValueError("splitter_unknown")
        value = self._database.setting(f"ui_{name}_splitter", "")
        try:
            return bytes.fromhex(value) if value else None
        except ValueError:
            return None

    def save_splitter_state(self, name: str, state: bytes) -> None:
        if name not in {"recognition_horizontal", "recognition_vertical"}:
            raise ValueError("splitter_unknown")
        self._database.set_setting(f"ui_{name}_splitter", state.hex())

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
        try:
            return int(self._database.setting("api_port", "4556"))
        except ValueError:
            return 4556

    def save_api_settings(self, enabled: bool, port: int) -> None:
        if not 1024 <= port <= 65535:
            raise ValueError("api_port_invalid")
        self._database.set_setting("api_enabled", "yes" if enabled else "no")
        self._database.set_setting("api_port", str(port))

    def issue_api_key(
        self, name: str, note: str, expires_at: str | None, min_interval_ms: int
    ) -> str:
        if not name.strip():
            raise ValueError("api_key_name_required")
        if min_interval_ms not in (200, 500, 1000, 2000):
            raise ValueError("api_rate_invalid")
        token = "sv_" + secrets.token_urlsafe(32)
        self._database.create_api_key(
            name.strip(),
            note.strip(),
            hashlib.sha256(token.encode()).hexdigest(),
            token[:12],
            expires_at,
            min_interval_ms,
        )
        return token

    def api_keys(self) -> list[sqlite3.Row]:
        return self._database.api_keys()

    def revoke_api_key(self, key_id: str) -> None:
        self._database.revoke_api_key(key_id)

    def api_audit(self) -> list[sqlite3.Row]:
        return self._database.api_audit()

    def setup_required(self) -> bool:
        return self._database.setting("license_accepted") != "yes" or self.image_directory() is None

    def complete_setup(self, image_directory: Path) -> None:
        if not image_directory.is_dir():
            raise ValueError("folder_missing")
        self.save_settings(image_directory)
        self._database.set_setting("license_accepted", "yes")

    def register_launch(self) -> int:
        return self._database.register_launch()

    def startup_log_path(self) -> Path:
        return self._database.path.parent / "startup.log"

    def app_data_directory(self) -> Path:
        return self._database.path.parent

    def log_startup(self, message: str) -> OSError | None:
        try:
            with self.startup_log_path().open("a", encoding="utf-8") as log:
                log.write(f"{datetime.now(UTC).isoformat()} {message}\n")
        except OSError as error:
            return error
        return None

    def locale(self) -> str:
        return (
            self._database.setting("locale", system_locale())
            if self._database.has_setting("locale")
            else system_locale()
        )

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

    def update_ai_agent(
        self, agent_id: str, name: str, provider: str, model: str, token: str
    ) -> None:
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
            raise RuntimeError("ai_profile_missing")
        token = keyring.get_password("Serial Vision", agent["credential_id"])
        if not token:
            raise RuntimeError("profile_key_required")
        return AiVisionRecognizer().recognize(agent["provider"], agent["model"], token, image_path)

    def models(self) -> list[sqlite3.Row]:
        return self._database.models()

    def popular_models(self) -> list[sqlite3.Row]:
        return self._database.popular_models()

    def add_model(self, name: object, device_type: object, service: object) -> None:
        validated_name, validated_type, validated_service = self._validate_model(
            name, device_type, service
        )
        try:
            self._database.save_model(None, validated_name, validated_type, validated_service)
        except sqlite3.IntegrityError as error:
            raise ValueError("model_exists") from error

    def update_model(
        self, model_id: int, name: object, device_type: object, service: object
    ) -> None:
        validated_name, validated_type, validated_service = self._validate_model(
            name, device_type, service
        )
        try:
            self._database.save_model(model_id, validated_name, validated_type, validated_service)
        except sqlite3.IntegrityError as error:
            raise ValueError("model_exists") from error

    @staticmethod
    def _validate_model(name: object, device_type: object, service: object) -> tuple[str, str, str]:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("model_name_required")
        if not isinstance(device_type, str) or device_type not in ("modem", "tuner"):
            raise ValueError("model_type_invalid")
        if not isinstance(service, str) or service not in ("internet", "television"):
            raise ValueError("model_service_invalid")
        return name.strip(), device_type, service

    def import_models_xlsx(self, path: Path) -> ImportSummary:
        imported = read_models_xlsx(path)
        existing = {
            (str(row["name"]).casefold(), str(row["device_type"]), str(row["service"]))
            for row in self.models()
        }
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
        copy = dict(data)
        copy.setdefault("source_image_path", self._database.source_image_path(device_id) or "")
        self._database.save_device(device_id, self._utc_device_data(copy))

    def _validate_device_data(self, data: dict[str, object]) -> None:
        text = data.get("recognized_text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("recognized_text_required")
        contract = data.get("contract_number")
        if contract is not None and not isinstance(contract, str):
            raise ValueError("contract_invalid")
        if len((contract or "").strip()) > 20:
            raise ValueError("contract_too_long")
        if data.get("operation_type") not in ("receipt", "issue"):
            raise ValueError("operation_invalid")
        model_id = data.get("device_model_id")
        if type(model_id) is not int or not self._database.model_exists(model_id):
            raise ValueError("model_required")
        timestamp = data.get("registered_at")
        try:
            if not isinstance(timestamp, str):
                raise ValueError
            datetime.fromisoformat(timestamp)
        except ValueError as error:
            raise ValueError("registered_at_invalid") from error
        source = data.get("source_image_path")
        if source is not None and not isinstance(source, str):
            raise ValueError("source_image_invalid")

    @staticmethod
    def _utc_device_data(data: dict[str, object]) -> dict[str, object]:
        copy = dict(data)
        copy["contract_number"] = copy.get("contract_number") or ""
        copy["source_image_path"] = copy.get("source_image_path") or ""
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

    def devices(
        self,
        search: str = "",
        device_type: str = "",
        service: str = "",
        date_from: str = "",
        date_to: str = "",
        model_id: int | None = None,
        operation: str = "",
        page: int = 1,
    ) -> tuple[list[sqlite3.Row], dict[str, int] | None]:
        return self._database.devices(
            search, device_type, service, date_from, date_to, model_id, operation, page
        )

    def all_filtered_devices(
        self,
        search: str = "",
        device_type: str = "",
        service: str = "",
        date_from: str = "",
        date_to: str = "",
        model_id: int | None = None,
        operation: str = "",
    ) -> list[sqlite3.Row]:
        rows, _ = self._database.devices(
            search, device_type, service, date_from, date_to, model_id, operation, 1, 10_000_000
        )
        return rows

    def export_devices(self, destination: Path, rows: list[sqlite3.Row]) -> None:
        self._database.export_csv(destination, rows)

    def statistics_summary(self, group_by: str = "month") -> StatisticsSummary:
        return self._database.statistics_summary(group_by)

    def statistics(self) -> list[sqlite3.Row]:
        return self._database.statistics()
