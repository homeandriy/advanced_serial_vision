from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsValues:
    """Editable settings snapshot; the service validates text input before writing."""

    locale: str
    image_directory: str
    theme: str
    icon_style: str
    rotate: bool
    enhance: bool
    api_enabled: bool
    api_port: str


class SettingsSaveError(RuntimeError):
    """A database/runtime failure aborted the atomic settings operation."""


class SettingsRecoveryError(SettingsSaveError):
    def __init__(self, original: Exception, recovery: Exception) -> None:
        super().__init__("settings_api_restore_failed")
        self.original = original
        self.recovery = recovery
