from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from serial_vision.application_service import SerialVisionService
from serial_vision.barcode import BarcodeRecognizer, extract_printed_codes
from serial_vision.i18n import error_message, system_locale
from serial_vision.ocr import RapidOcrRecognizer
from serial_vision.recognition_strategies import RecognitionOptions
from serial_vision.updates import (
    ReleaseInfo,
    check_latest_release,
    download_linux_update,
    download_update,
    write_update_log,
)


class UpdateWorker(QThread):
    checked = Signal(object)
    failed = Signal(str)

    def __init__(self, repository: str, current_version: str, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.current_version = current_version

    def run(self) -> None:
        try:
            self.checked.emit(check_latest_release(self.repository, self.current_version))
        except Exception as error:
            self.failed.emit(str(error))


class UpdateDownloadWorker(QThread):
    completed = Signal(str)
    failed = Signal(str)
    progress = Signal(int, object, str)
    phase = Signal(str)

    def __init__(self, release: ReleaseInfo, target: str, log_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.release = release
        self.target = target
        self.log_path = log_path

    def run(self) -> None:
        try:
            downloader = download_update if self.target == "windows" else download_linux_update
            source = (
                self.release.installer_url
                if self.target == "windows"
                else self.release.linux_package_url
            )
            write_update_log(self.log_path, f"Downloading update from {source}")
            self.completed.emit(
                str(downloader(self.release, self.progress.emit, self.download_phase))
            )
        except Exception as error:
            write_update_log(self.log_path, f"Update download failed: {error}")
            self.failed.emit(str(error))

    def download_phase(self, phase: str) -> None:
        write_update_log(self.log_path, f"Update phase: {phase}")
        self.phase.emit(phase)


class RecognitionWorker(QThread):
    completed = Signal(str, str, str, str)
    stage = Signal(str)
    cancelled = Signal(str)

    def __init__(
        self,
        image_path: Path,
        language: str,
        barcode_fallback_label: str,
        barcode_module_unavailable: str,
        options: RecognitionOptions,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.image_path = image_path
        self.language = language
        self.barcode_fallback_label = barcode_fallback_label
        self.barcode_module_unavailable = barcode_module_unavailable
        self.options = options
        self.locale = getattr(parent, "locale", None) or system_locale()

    def run(self) -> None:
        if self.isInterruptionRequested():
            self.cancelled.emit(str(self.image_path))
            return
        ocr_text = ""
        barcode_text = ""
        self.stage.emit("ocr")
        try:
            ocr_text = RapidOcrRecognizer(self.language, self.options).recognize(self.image_path)
        except Exception as error:
            ocr_text = error_message(self.locale, error)
        if self.isInterruptionRequested():
            self.cancelled.emit(str(self.image_path))
            return
        self.stage.emit("barcode")
        try:
            barcode_text = BarcodeRecognizer(
                self.barcode_module_unavailable, self.options
            ).recognize(self.image_path)
        except Exception as error:
            barcode_text = error_message(self.locale, error)
        if self.isInterruptionRequested():
            self.cancelled.emit(str(self.image_path))
            return
        decoded_values = {
            line.partition(": ")[2] for line in barcode_text.splitlines() if ": " in line
        }
        fallback_values = [
            value for value in extract_printed_codes(ocr_text) if value not in decoded_values
        ]
        if fallback_values:
            fallback_text = "\n".join(
                f"{self.barcode_fallback_label}: {value}" for value in fallback_values
            )
            barcode_text = "\n".join(value for value in (barcode_text, fallback_text) if value)
        self.completed.emit(str(self.image_path), ocr_text, barcode_text, "")


class AiRecognitionWorker(QThread):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(
        self, service: SerialVisionService, agent_id: str, image_path: Path, parent=None
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.agent_id = agent_id
        self.image_path = image_path

    def run(self) -> None:
        try:
            self.completed.emit(self.service.recognize_ai(self.agent_id, self.image_path))
        except Exception as error:
            self.failed.emit(error_message(self.service.locale(), error))
