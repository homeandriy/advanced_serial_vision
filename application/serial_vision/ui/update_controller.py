from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QDesktopServices, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from serial_vision.application_service import SerialVisionService
from serial_vision.i18n import error_message, t
from serial_vision.ui.buttons import button
from serial_vision.ui.workers import (
    UpdateDownloadWorker,
    UpdateWorker,
)
from serial_vision.updates import (
    ReleaseInfo,
    create_update_log,
    launch_update,
    write_update_log,
)
from serial_vision.version import app_version


class UpdateController(QObject):
    close_requested = Signal()

    def __init__(self, service: SerialVisionService, locale: str, window: QWidget) -> None:
        super().__init__(window)
        self.window, self.service, self.ui_locale = window, service, locale
        self._closing = False
        self.update_worker: UpdateWorker | None = None
        self._dismissed_update_version: str | None = None
        self.update_check_timer = QTimer(self)
        self.update_check_timer.setInterval(4 * 60 * 60 * 1_000)
        self.update_check_timer.timeout.connect(self.check_updates_silently)
        self.update_check_timer.start()
        QTimer.singleShot(60_000, self.check_updates_silently)

    def stop(self) -> None:
        self._closing = True
        self.update_check_timer.stop()

    def translate(self, key: str, **values: object) -> str:
        return t(self.ui_locale, key, **values)

    def check_updates(self) -> None:
        self.start_update_check(show_status=True)

    def check_updates_silently(self) -> None:
        self.start_update_check(show_status=False)

    def start_update_check(self, show_status: bool) -> None:
        if self._closing:
            return
        repository = self.service.update_repository()
        if not repository:
            if show_status:
                QMessageBox.information(
                    self.window, self.translate("help"), self.translate("update_not_configured")
                )
            return
        if self.update_worker is not None and self.update_worker.isRunning():
            return
        self.update_worker = UpdateWorker(repository, app_version(), self)
        self.update_worker.checked.connect(
            lambda release: self.update_checked(release, show_status)
        )
        self.update_worker.failed.connect(lambda error: self.update_failed(error, show_status))
        self.update_worker.start()

    def update_checked(self, release: ReleaseInfo | None, show_status: bool) -> None:
        if self._closing:
            return
        if release is None:
            if show_status:
                QMessageBox.information(
                    self.window, self.translate("help"), self.translate("update_not_found")
                )
            return
        if not show_status and release.version == self._dismissed_update_version:
            return
        self.show_update_dialog(release)

    def show_update_dialog(self, release: ReleaseInfo) -> None:
        dialog = QDialog(self.window)
        dialog.setWindowTitle(self.translate("update_available_title", version=release.version))
        dialog.setWindowIcon(self.window.windowIcon())
        layout = QVBoxLayout(dialog)
        details = QLabel(
            self.translate("update_available_details", version=release.version), dialog
        )
        details.setWordWrap(True)
        layout.addWidget(details)
        layout.addWidget(QLabel(self.translate("update_release_notes"), dialog))
        changelog = QTextEdit(dialog)
        changelog.setReadOnly(True)
        changelog.setPlainText(release.changelog.strip() or self.translate("update_no_changelog"))
        layout.addWidget(changelog, 1)
        actions = QHBoxLayout()
        actions.addStretch()
        if sys.platform == "win32" and release.installer_url:
            install = button(dialog, "download", self.translate("download_and_install"))
            install.clicked.connect(lambda: self.download_and_install_update(release, dialog))
            actions.addWidget(install)
        elif sys.platform.startswith("linux") and release.linux_package_url:
            install = button(dialog, "download", self.translate("download_deb"))
            install.clicked.connect(lambda: self.download_and_open_linux_update(release, dialog))
            actions.addWidget(install)
        elif release.release_url:
            open_release = button(dialog, "open", self.translate("open_release"))
            open_release.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl(release.release_url))
            )
            actions.addWidget(open_release)
        later = button(dialog, "close", self.translate("later"))
        later.clicked.connect(dialog.reject)
        actions.addWidget(later)
        layout.addLayout(actions)
        dialog.resize(620, 460)
        if dialog.exec() == QDialog.DialogCode.Rejected:
            self._dismissed_update_version = release.version

    def download_and_install_update(self, release: ReleaseInfo, dialog: QDialog) -> None:
        dialog.accept()
        self.start_update_download(release, "windows")

    def download_and_open_linux_update(self, release: ReleaseInfo, dialog: QDialog) -> None:
        dialog.accept()
        self.start_update_download(release, "linux")

    def start_update_download(self, release: ReleaseInfo, target: str) -> None:
        self.update_download_target = target
        self.update_log_path = create_update_log(self.service.app_data_directory())
        source_url = release.installer_url if target == "windows" else release.linux_package_url
        write_update_log(
            self.update_log_path, f"Selected release v{release.version}; source: {source_url}"
        )
        self.update_progress = QDialog(self.window)
        self.update_progress.setWindowTitle(
            self.translate("update_progress_title", version=release.version)
        )
        self.update_progress.setWindowIcon(self.window.windowIcon())
        self.update_progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.update_progress.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        layout = QVBoxLayout(self.update_progress)
        self.update_steps = [
            QLabel(self.translate("update_step_download"), self.update_progress),
            QLabel(self.translate("update_step_prepare"), self.update_progress),
            QLabel(self.translate("update_step_close"), self.update_progress),
        ]
        self.update_steps[0].setObjectName("updateStepActive")
        for step in self.update_steps:
            step.setWordWrap(True)
            layout.addWidget(step)
        source = QLabel(
            self.translate(
                "update_source", url=source_url or self.translate("update_source_unknown")
            ),
            self.update_progress,
        )
        source.setWordWrap(True)
        source.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(source)
        self.update_download_status = QLabel(
            self.translate("update_download_starting"), self.update_progress
        )
        self.update_download_status.setWordWrap(True)
        layout.addWidget(self.update_download_status)
        self.update_progress_bar = QProgressBar(self.update_progress)
        self.update_progress_bar.setRange(0, 100)
        self.update_progress_bar.setValue(0)
        layout.addWidget(self.update_progress_bar)
        self.update_log_view = QTextEdit(self.update_progress)
        self.update_log_view.setReadOnly(True)
        self.update_log_view.setMinimumHeight(120)
        layout.addWidget(self.update_log_view)
        actions = QHBoxLayout()
        self.update_open_log = button(
            self.update_progress, "open", self.translate("open_update_log")
        )
        self.update_open_log.clicked.connect(self.open_update_log)
        self.update_close = button(self.update_progress, "close", self.translate("close"))
        self.update_close.setEnabled(False)
        self.update_close.clicked.connect(self.update_progress.reject)
        actions.addWidget(self.update_open_log)
        actions.addStretch()
        actions.addWidget(self.update_close)
        layout.addLayout(actions)
        self.update_progress.setMinimumWidth(450)
        self.update_progress.resize(560, 470)
        self.refresh_update_log()
        self.update_progress.show()
        self.update_download_worker = UpdateDownloadWorker(
            release, target, self.update_log_path, self
        )
        self.update_download_worker.progress.connect(self.update_download_progress)
        self.update_download_worker.phase.connect(self.update_download_phase)
        self.update_download_worker.completed.connect(self.update_downloaded)
        self.update_download_worker.failed.connect(self.update_download_failed)
        self.update_download_worker.start()

    def update_download_progress(self, downloaded: int, total: int | None, _url: str) -> None:
        if total and total > 0:
            percent = min(50, int(downloaded * 50 / total))
            self.update_progress_bar.setValue(percent)
            self.update_download_status.setText(
                self.translate(
                    "update_download_status",
                    downloaded=f"{downloaded / 1024 / 1024:.1f}",
                    total=f"{total / 1024 / 1024:.1f}",
                    percent=str(int(downloaded * 100 / total)),
                )
            )
            return
        self.update_progress_bar.setValue(min(49, self.update_progress_bar.value() + 1))
        self.update_download_status.setText(
            self.translate(
                "update_download_status_unknown", downloaded=f"{downloaded / 1024 / 1024:.1f}"
            )
        )

    def update_download_phase(self, phase: str) -> None:
        if phase == "verifying":
            write_update_log(self.update_log_path, "Download completed. Verifying SHA-256 digest.")
            self.refresh_update_log()
            self.update_progress_bar.setValue(50)
            self.update_download_status.setText(self.translate("update_verifying"))
            self.set_update_step(0, "done")
            self.set_update_step(1, "active")

    def set_update_step(self, index: int, state: str) -> None:
        self.update_steps[index].setObjectName(
            {"active": "updateStepActive", "done": "updateStepDone"}.get(state, "")
        )
        self.update_steps[index].style().unpolish(self.update_steps[index])
        self.update_steps[index].style().polish(self.update_steps[index])

    def refresh_update_log(self) -> None:
        try:
            self.update_log_view.setPlainText(self.update_log_path.read_text(encoding="utf-8"))
            self.update_log_view.moveCursor(QTextCursor.MoveOperation.End)
        except OSError as error:
            self.update_log_view.setPlainText(str(error))

    def open_update_log(self) -> None:
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.update_log_path))):
            QMessageBox.warning(
                self.window,
                self.translate("error"),
                self.translate("update_log_open_failed", path=str(self.update_log_path)),
            )

    def update_downloaded(self, installer_path: str) -> None:
        if self._closing:
            return
        self.update_progress_bar.setValue(75)
        self.set_update_step(1, "done")
        write_update_log(self.update_log_path, f"Downloaded and verified asset: {installer_path}")
        self.refresh_update_log()
        if self.update_download_target == "linux":
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(installer_path)):
                self.update_close.setEnabled(True)
                QMessageBox.warning(
                    self.window,
                    self.translate("error"),
                    self.translate("linux_update_open_failed", path=installer_path),
                )
                return
            self.update_progress_bar.setValue(100)
            self.set_update_step(2, "done")
            write_update_log(self.update_log_path, "Linux package opened in the system installer.")
            self.refresh_update_log()
            self.update_progress.accept()
            QMessageBox.information(
                self.window,
                self.translate("help"),
                self.translate("linux_update_ready", path=installer_path),
            )
            return
        try:
            self.set_update_step(2, "active")
            self.update_progress_bar.setValue(100)
            self.update_download_status.setText(self.translate("update_closing_application"))
            write_update_log(
                self.update_log_path,
                "Starting visible installer directly; application will now close.",
            )
            self.refresh_update_log()
            launch_update(Path(installer_path), self.update_log_path)
        except RuntimeError as error:
            self.update_close.setEnabled(True)
            write_update_log(self.update_log_path, f"Could not start updater helper: {error}")
            QMessageBox.warning(self.window, self.translate("error"), self.translate(str(error)))
            return
        QTimer.singleShot(1_000, self.finish_windows_update)

    def finish_windows_update(self) -> None:
        self.service.log_startup(
            "Visible update installer started; closing application for file replacement."
        )
        self.close_requested.emit()

    def update_download_failed(self, error: str) -> None:
        if self._closing:
            return
        error = error_message(self.ui_locale, error)
        self.update_close.setEnabled(True)
        self.update_download_status.setText(self.translate("update_download_failed", error=error))
        QMessageBox.warning(
            self.window,
            self.translate("error"),
            self.translate("update_download_failed", error=error),
        )

    def update_failed(self, error: str, show_status: bool) -> None:
        if self._closing:
            return
        self.service.log_startup(f"Update check failed: {error}")
        if show_status:
            QMessageBox.warning(self.window, self.translate("error"), error)
