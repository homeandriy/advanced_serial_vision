from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtMultimedia import QCamera, QImageCapture, QMediaCaptureSession, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from serial_vision.application_service import SerialVisionService
from serial_vision.ui.buttons import button
from serial_vision.ui.pages.base import Page
from serial_vision.ui.workers import CameraScanWorker


class CameraPage(Page):
    def __init__(
        self, service: SerialVisionService, locale: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(service, locale, parent)
        self._closing = False
        self.scan_worker: CameraScanWorker | None = None
        self.camera: QCamera | None = None
        self.camera_capture: QImageCapture | None = None
        self.camera_session: QMediaCaptureSession | None = None
        self.install(self.camera_scan())

    def camera_scan(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        self.camera_selector = QComboBox(page)
        self.camera_refresh = button(page, "refresh", self.translate("camera_refresh"))
        self.camera_refresh.clicked.connect(self.refresh_camera_devices)
        self.camera_start = button(page, "camera", self.translate("camera_start"))
        self.camera_start.clicked.connect(self.start_camera)
        self.camera_stop_button = button(page, "stop", self.translate("camera_stop"))
        self.camera_stop_button.clicked.connect(self.stop_camera)
        self.camera_capture_button = button(page, "capture", self.translate("camera_capture"))
        self.camera_capture_button.clicked.connect(self.capture_camera_frame)
        controls.addWidget(QLabel(self.translate("camera")))
        controls.addWidget(self.camera_selector, 1)
        controls.addWidget(self.camera_refresh)
        controls.addWidget(self.camera_start)
        controls.addWidget(self.camera_stop_button)
        controls.addWidget(self.camera_capture_button)
        layout.addLayout(controls)
        self.camera_status = QLabel(self.translate("camera_unavailable"), page)
        self.camera_status.setWordWrap(True)
        layout.addWidget(self.camera_status)
        self.camera_view = QVideoWidget(page)
        self.camera_view.setMinimumHeight(360)
        layout.addWidget(self.camera_view, 1)
        layout.addWidget(QLabel(self.translate("camera_result"), page))
        self.camera_result = QTextEdit(page)
        self.camera_result.setReadOnly(True)
        self.bind_result_menu(self.camera_result)
        layout.addWidget(self.camera_result, 1)
        self.refresh_camera_devices()
        return page

    def refresh_camera_devices(self) -> None:
        self.stop_camera()
        self.camera_selector.clear()
        for device in QMediaDevices.videoInputs():
            self.camera_selector.addItem(device.description(), device)
        available = self.camera_selector.count() > 0
        self.camera_start.setEnabled(available)
        self.camera_stop_button.setEnabled(False)
        self.camera_capture_button.setEnabled(False)
        self.camera_status.setText(
            self.translate("camera_select") if available else self.translate("camera_unavailable")
        )

    def start_camera(self) -> None:
        device = self.camera_selector.currentData()
        if device is None:
            self.camera_status.setText(self.translate("camera_unavailable"))
            return
        self.stop_camera(update_status=False)
        try:
            self.camera = QCamera(device, self)
            self.camera_capture = QImageCapture(self)
            self.camera_capture.imageSaved.connect(self.camera_image_saved)
            self.camera_capture.errorOccurred.connect(
                lambda *_args: self.camera_status.setText(
                    self.translate("camera_error", error=str(_args[-1]))
                )
            )
            self.camera_session = QMediaCaptureSession(self)
            self.camera_session.setCamera(self.camera)
            self.camera_session.setVideoOutput(self.camera_view)
            self.camera_session.setImageCapture(self.camera_capture)
            self.camera.start()
        except RuntimeError as error:
            self.stop_camera()
            self.camera_status.setText(self.translate("camera_error", error=str(error)))
            return
        self.camera_start.setEnabled(False)
        self.camera_stop_button.setEnabled(True)
        self.camera_capture_button.setEnabled(True)
        self.camera_status.setText(self.translate("camera_ready"))

    def stop_camera(self, *, update_status: bool = True) -> None:
        if self.camera is not None:
            self.camera.stop()
        self.camera = None
        self.camera_capture = None
        self.camera_session = None
        if hasattr(self, "camera_capture_button"):
            available = self.camera_selector.count() > 0
            self.camera_start.setEnabled(available)
            self.camera_stop_button.setEnabled(False)
            self.camera_capture_button.setEnabled(False)
            if update_status:
                self.camera_status.setText(
                    self.translate("camera_stopped")
                    if available
                    else self.translate("camera_unavailable")
                )

    def begin_shutdown(self) -> None:
        self._closing = True
        self.stop_camera(update_status=False)

    def capture_camera_frame(self) -> None:
        if self.scan_worker is not None and self.scan_worker.isRunning():
            return
        if self.camera_capture is None:
            self.camera_status.setText(self.translate("camera_unavailable"))
            return
        destination = (
            Path(tempfile.gettempdir())
            / f"advanced-serial-vision-scan-{datetime.now().strftime('%Y%m%d%H%M%S%f')}.jpg"
        )
        self.camera_status.setText(self.translate("camera_capturing"))
        self.camera_capture.captureToFile(str(destination))

    def camera_image_saved(self, _request_id: int, filename: str) -> None:
        worker = CameraScanWorker(
            Path(filename),
            self.service.recognition_options(),
            self.translate("barcode_module_unavailable"),
            self,
        )
        self.scan_worker = worker
        self.camera_capture_button.setEnabled(False)
        worker.completed.connect(self.scan_completed)
        worker.failed.connect(self.scan_failed)
        worker.finished.connect(lambda: self.scan_finished(worker))
        if self._closing:
            worker.requestInterruption()
        worker.start()

    def scan_completed(self, result: str) -> None:
        if not self._closing:
            self.camera_result.setPlainText(result or self.translate("camera_result_empty"))
            self.camera_status.setText(self.translate("camera_ready"))

    def scan_failed(self, error: str) -> None:
        if not self._closing:
            self.camera_status.setText(self.translate("camera_error", error=error))

    def scan_finished(self, worker: CameraScanWorker) -> None:
        if self.scan_worker is worker:
            self.scan_worker = None
        worker.deleteLater()
        if not self._closing:
            self.camera_capture_button.setEnabled(self.camera_capture is not None)
