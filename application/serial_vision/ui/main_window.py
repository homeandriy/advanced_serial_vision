from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QValueAxis
from PySide6.QtCore import (
    QByteArray,
    QDate,
    QDateTime,
    QEvent,
    QLocale,
    QSize,
    Qt,
    QThread,
    QTimer,
    QUrl,
)
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QIcon, QPixmap, QTextCursor
from PySide6.QtMultimedia import QCamera, QImageCapture, QMediaCaptureSession, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStyle,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from serial_vision.application_service import SerialVisionService
from serial_vision.barcode import BarcodeRecognizer
from serial_vision.i18n import SUPPORTED_LOCALES, error_message, t
from serial_vision.image_catalog import ImageCatalog
from serial_vision.local_api import LocalApiServer
from serial_vision.recognition_strategies import RecognitionOptions
from serial_vision.ui.buttons import apply_button_icons, button, icon_for, icon_size
from serial_vision.ui.help_dialog import HelpDialog
from serial_vision.ui.image_editor import ImageEditorDialog
from serial_vision.ui.photo_preview import PhotoPreview
from serial_vision.ui.theme import apply_theme
from serial_vision.ui.workers import (
    AiRecognitionWorker,
    RecognitionWorker,
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


@dataclass(frozen=True)
class SettingsValues:
    locale: str
    image_directory: str
    theme: str
    icon_style: str
    rotate: bool
    enhance: bool
    api_enabled: bool
    api_port: str


class MainWindow(QMainWindow):
    def __init__(self, service: SerialVisionService) -> None:
        super().__init__()
        self.service = service
        self.local_api = LocalApiServer(service)
        self.locale = service.locale()
        self.catalog = ImageCatalog(service.image_directory())
        self.selected_image: Path | None = None
        self.image_page = 1
        self.equipment_page = 1
        self.camera: QCamera | None = None
        self.camera_capture: QImageCapture | None = None
        self.camera_session: QMediaCaptureSession | None = None
        self._closing = False
        self._ai_busy = False
        self._ai_generation = 0
        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setInterval(50)
        self._shutdown_timer.timeout.connect(self.close)
        self.service.register_launch()
        self.startup_log_error = self.service.log_startup("Application startup started")
        self.setWindowTitle(self.tr("app_name"))
        self.setWindowIcon(self.icon())
        self.resize(1500, 920)
        self.create_tray()
        self.create_menus()
        self.recognition_generation = 0
        self._recognition_workers: set[RecognitionWorker] = set()
        self._recognition_busy = False
        self.tabs = QTabWidget()
        self.tabs.setIconSize(icon_size(self.service.icon_style()))
        self.setCentralWidget(self.tabs)
        self.tabs.addTab(self.recognition(), self.tab_icon("recognition"), self.tr("recognition"))
        self.tabs.addTab(self.equipment(), self.tab_icon("equipment"), self.tr("equipment"))
        self.tabs.addTab(self.models(), self.tab_icon("models"), self.tr("models"))
        self.tabs.addTab(self.statistics(), self.tab_icon("statistics"), self.tr("statistics"))
        self.camera_tab = self.camera_scan()
        self.tabs.addTab(self.camera_tab, self.tab_icon("scan"), self.tr("scan"))
        self.api_integration_tab = self.api_integrations()
        self.tabs.addTab(
            self.api_integration_tab, self.tab_icon("api_integrations"), self.tr("api_integrations")
        )
        self.api_integration_tab.setEnabled(self.service.api_enabled())
        self.tabs.addTab(self.settings(), self.tab_icon("settings"), self.tr("settings"))
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.refresh_images()
        self.refresh_agents()
        self.refresh_equipment()
        self.refresh_models()
        self.refresh_statistics()
        self.refresh_api_integration()
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().addPermanentWidget(
            QLabel(f"{self.tr('developer')}  •  {self.tr('version', version=app_version())}")
        )
        QTimer.singleShot(0, self.restore_splitters)
        if self.service.api_enabled():
            try:
                self.local_api.start()
            except OSError as error:
                QTimer.singleShot(
                    0,
                    lambda message=str(error): QMessageBox.warning(
                        self, self.tr("error"), self.tr("api_start_failed", error=message)
                    ),
                )
        if self.startup_log_error is None:
            self.service.log_startup("Main window is ready")
        else:
            QTimer.singleShot(0, self.retry_startup_log)
        self._dismissed_update_version: str | None = None
        self.update_check_timer = QTimer(self)
        self.update_check_timer.setInterval(4 * 60 * 60 * 1_000)
        self.update_check_timer.timeout.connect(self.check_updates_silently)
        self.update_check_timer.start()
        QTimer.singleShot(60_000, self.check_updates_silently)
        self.show_first_run_setup() if self.service.setup_required() else None

    def tr(self, key: str, **values: str) -> str:
        return t(self.locale, key, **values)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._closing:
            self._closing = True
            self.update_check_timer.stop()
            self.stop_camera(update_status=False)
            self.local_api.stop()
            editor = getattr(self, "image_editor", None)
            if editor is not None:
                editor.close()
            self.setEnabled(False)
            self.statusBar().showMessage(self.tr("shutdown_wait"))
        workers = [worker for worker in self.findChildren(QThread) if worker.isRunning()]
        for worker in workers:
            worker.requestInterruption()
        if workers:
            event.ignore()
            self._shutdown_timer.start()
            return
        self._shutdown_timer.stop()
        self.tray.hide()
        event.accept()
        QApplication.quit()

    def icon(self) -> QIcon:
        return QIcon(str(Path(__file__).parents[1] / "assets" / "app-icon.png"))

    def eventFilter(self, watched, event) -> bool:
        if watched is self.image_cards.viewport() and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self.relayout_image_cards)
        return super().eventFilter(watched, event)

    def restore_splitters(self) -> None:
        for name, splitter in (
            ("recognition_horizontal", self.photo_splitter),
            ("recognition_vertical", self.image_splitter),
        ):
            state = self.service.splitter_state(name)
            if state:
                splitter.restoreState(QByteArray(state))
            splitter.splitterMoved.connect(
                lambda _position,
                _index,
                key=name,
                control=splitter: self.service.save_splitter_state(key, bytes(control.saveState()))
            )

    def retry_startup_log(self) -> None:
        error = self.service.log_startup(self.tr("startup_log_retry"))
        if error is not None:
            QMessageBox.warning(
                self,
                self.tr("error"),
                self.tr(
                    "startup_log_unavailable",
                    path=str(self.service.startup_log_path().parent),
                    error=str(error),
                ),
            )

    def tab_icon(self, name: str) -> QIcon:
        return icon_for(self, name)

    def create_tray(self) -> None:
        self.tray = QSystemTrayIcon(self.icon(), self)
        self.tray.setToolTip(self.tr("app_name"))
        menu = QMenu(self)
        show = QAction(self.tr("open"), self)
        show.triggered.connect(self.showNormal)
        exit_action = QAction(self.tr("exit"), self)
        exit_action.triggered.connect(self.close)
        menu.addActions([show, exit_action])
        self.tray.setContextMenu(menu)
        self.tray.show()

    def create_menus(self) -> None:
        file_menu = self.menuBar().addMenu(self.tr("menu_file"))
        choose = file_menu.addAction(self.tr("choose_folder"))
        choose.triggered.connect(self.choose_folder)
        open_action = file_menu.addAction(self.tr("open_folder"))
        open_action.triggered.connect(self.open_folder)
        file_menu.addSeparator()
        exit_action = file_menu.addAction(self.tr("exit"))
        exit_action.triggered.connect(self.close)

        edit_menu = self.menuBar().addMenu(self.tr("menu_edit"))
        copy_action = edit_menu.addAction(self.tr("copy"))
        copy_action.triggered.connect(self.copy_active_text)
        rotate_action = edit_menu.addAction(self.tr("rotate"))
        rotate_action.triggered.connect(self.rotate)
        delete_action = edit_menu.addAction(self.tr("delete"))
        delete_action.triggered.connect(self.delete_image)

        view_menu = self.menuBar().addMenu(self.tr("menu_view"))
        for index, key in enumerate(
            (
                "recognition",
                "equipment",
                "models",
                "statistics",
                "scan",
                "api_integrations",
                "settings",
            )
        ):
            action = view_menu.addAction(self.tr(key))
            action.triggered.connect(
                lambda _checked=False, current=index: self.tabs.setCurrentIndex(current)
            )

        help_menu = self.menuBar().addMenu(self.tr("help"))
        help_action = help_menu.addAction(self.tr("help_contents"))
        help_action.triggered.connect(self.show_help)
        log_action = help_menu.addAction(self.tr("startup_log"))
        log_action.triggered.connect(self.open_startup_log)
        update_action = help_menu.addAction(self.tr("check_updates"))
        update_action.triggered.connect(self.check_updates)
        about_action = help_menu.addAction(self.tr("about"))
        about_action.triggered.connect(self.show_about)

    def show_about(self) -> None:
        website_url = "https://webbooks.com.ua/portfolio-uk/?utm_source=webbooks&utm_medium=sidebar&utm_campaign=portfolio"
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("about"))
        dialog.setWindowIcon(self.icon())
        dialog.setMinimumWidth(760)
        layout = QVBoxLayout(dialog)

        header = QHBoxLayout()
        logo = QLabel(dialog)
        logo.setPixmap(self.icon().pixmap(QSize(56, 56)))
        logo.setAccessibleName(self.tr("app_name"))
        header.addWidget(logo)
        description = QLabel(
            f"<b>{self.tr('app_name')}</b><br>{self.tr('about_description')}", dialog
        )
        description.setWordWrap(True)
        header.addWidget(description, 1)
        layout.addLayout(header)

        details = QFormLayout()
        version = app_version()
        details.addRow(self.tr("version_label"), QLabel(f"v{version}", dialog))
        details.addRow(self.tr("developer_label"), QLabel("homeandriy", dialog))
        website = QLabel(
            '<a href="https://webbooks.com.ua/portfolio-uk/?utm_source=webbooks&amp;utm_medium=sidebar&amp;utm_campaign=portfolio">webbooks.com.ua/portfolio-uk</a>',
            dialog,
        )
        website.setOpenExternalLinks(True)
        details.addRow(self.tr("website"), website)
        layout.addLayout(details)

        actions = QHBoxLayout()
        actions.addStretch()
        open_website = button(dialog, "open", self.tr("open_website"))
        open_website.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(website_url)))
        close = button(dialog, "close", self.tr("close"))
        close.clicked.connect(dialog.accept)
        actions.addWidget(open_website)
        actions.addWidget(close)
        layout.addLayout(actions)
        dialog.resize(760, 300)
        dialog.exec()

    def show_help(self, section_id: str | None = None) -> None:
        HelpDialog(self.locale, section_id, self).exec()

    def help_button(self, section_id: str, title_key: str) -> QToolButton:
        control = QToolButton(self)
        control.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion))
        label = self.tr("open_help_section", section=self.tr(title_key))
        control.setToolTip(label)
        control.setAccessibleName(label)
        control.setAutoRaise(True)
        control.clicked.connect(lambda: self.show_help(section_id))
        return control

    def copy_active_text(self) -> None:
        focused = QApplication.focusWidget()
        if isinstance(focused, QTextEdit) and focused.textCursor().hasSelection():
            focused.copy()
            return
        QMessageBox.information(self, self.tr("help"), self.tr("select_text_to_copy"))

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
                QMessageBox.information(self, self.tr("help"), self.tr("update_not_configured"))
            return
        if getattr(self, "update_worker", None) and self.update_worker.isRunning():
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
                QMessageBox.information(self, self.tr("help"), self.tr("update_not_found"))
            return
        if not show_status and release.version == self._dismissed_update_version:
            return
        self.show_update_dialog(release)

    def show_update_dialog(self, release: ReleaseInfo) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("update_available_title", version=release.version))
        dialog.setWindowIcon(self.icon())
        layout = QVBoxLayout(dialog)
        details = QLabel(self.tr("update_available_details", version=release.version), dialog)
        details.setWordWrap(True)
        layout.addWidget(details)
        layout.addWidget(QLabel(self.tr("update_release_notes"), dialog))
        changelog = QTextEdit(dialog)
        changelog.setReadOnly(True)
        changelog.setPlainText(release.changelog.strip() or self.tr("update_no_changelog"))
        layout.addWidget(changelog, 1)
        actions = QHBoxLayout()
        actions.addStretch()
        if sys.platform == "win32" and release.installer_url:
            install = button(dialog, "download", self.tr("download_and_install"))
            install.clicked.connect(lambda: self.download_and_install_update(release, dialog))
            actions.addWidget(install)
        elif sys.platform.startswith("linux") and release.linux_package_url:
            install = button(dialog, "download", self.tr("download_deb"))
            install.clicked.connect(lambda: self.download_and_open_linux_update(release, dialog))
            actions.addWidget(install)
        elif release.release_url:
            open_release = button(dialog, "open", self.tr("open_release"))
            open_release.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl(release.release_url))
            )
            actions.addWidget(open_release)
        later = button(dialog, "close", self.tr("later"))
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
        self.update_progress = QDialog(self)
        self.update_progress.setWindowTitle(
            self.tr("update_progress_title", version=release.version)
        )
        self.update_progress.setWindowIcon(self.icon())
        self.update_progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.update_progress.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        layout = QVBoxLayout(self.update_progress)
        self.update_steps = [
            QLabel(self.tr("update_step_download"), self.update_progress),
            QLabel(self.tr("update_step_prepare"), self.update_progress),
            QLabel(self.tr("update_step_close"), self.update_progress),
        ]
        self.update_steps[0].setObjectName("updateStepActive")
        for step in self.update_steps:
            step.setWordWrap(True)
            layout.addWidget(step)
        source = QLabel(
            self.tr("update_source", url=source_url or self.tr("update_source_unknown")),
            self.update_progress,
        )
        source.setWordWrap(True)
        source.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(source)
        self.update_download_status = QLabel(
            self.tr("update_download_starting"), self.update_progress
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
        self.update_open_log = button(self.update_progress, "open", self.tr("open_update_log"))
        self.update_open_log.clicked.connect(self.open_update_log)
        self.update_close = button(self.update_progress, "close", self.tr("close"))
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
                self.tr(
                    "update_download_status",
                    downloaded=f"{downloaded / 1024 / 1024:.1f}",
                    total=f"{total / 1024 / 1024:.1f}",
                    percent=str(int(downloaded * 100 / total)),
                )
            )
            return
        self.update_progress_bar.setValue(min(49, self.update_progress_bar.value() + 1))
        self.update_download_status.setText(
            self.tr("update_download_status_unknown", downloaded=f"{downloaded / 1024 / 1024:.1f}")
        )

    def update_download_phase(self, phase: str) -> None:
        if phase == "verifying":
            write_update_log(self.update_log_path, "Download completed. Verifying SHA-256 digest.")
            self.refresh_update_log()
            self.update_progress_bar.setValue(50)
            self.update_download_status.setText(self.tr("update_verifying"))
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
                self,
                self.tr("error"),
                self.tr("update_log_open_failed", path=str(self.update_log_path)),
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
                    self, self.tr("error"), self.tr("linux_update_open_failed", path=installer_path)
                )
                return
            self.update_progress_bar.setValue(100)
            self.set_update_step(2, "done")
            write_update_log(self.update_log_path, "Linux package opened in the system installer.")
            self.refresh_update_log()
            self.update_progress.accept()
            QMessageBox.information(
                self, self.tr("help"), self.tr("linux_update_ready", path=installer_path)
            )
            return
        try:
            self.set_update_step(2, "active")
            self.update_progress_bar.setValue(100)
            self.update_download_status.setText(self.tr("update_closing_application"))
            write_update_log(
                self.update_log_path,
                "Starting visible installer directly; application will now close.",
            )
            self.refresh_update_log()
            launch_update(Path(installer_path), self.update_log_path)
        except RuntimeError as error:
            self.update_close.setEnabled(True)
            write_update_log(self.update_log_path, f"Could not start updater helper: {error}")
            QMessageBox.warning(self, self.tr("error"), self.tr(str(error)))
            return
        QTimer.singleShot(1_000, self.finish_windows_update)

    def finish_windows_update(self) -> None:
        self.service.log_startup(
            "Visible update installer started; closing application for file replacement."
        )
        self.close()

    def update_download_failed(self, error: str) -> None:
        if self._closing:
            return
        error = error_message(self.locale, error)
        self.update_close.setEnabled(True)
        self.update_download_status.setText(self.tr("update_download_failed", error=error))
        QMessageBox.warning(self, self.tr("error"), self.tr("update_download_failed", error=error))

    def update_failed(self, error: str, show_status: bool) -> None:
        if self._closing:
            return
        self.service.log_startup(f"Update check failed: {error}")
        if show_status:
            QMessageBox.warning(self, self.tr("error"), error)

    def open_startup_log(self) -> None:
        error = self.service.log_startup("User opened startup log")
        if error is not None:
            QMessageBox.warning(
                self,
                self.tr("error"),
                self.tr(
                    "startup_log_unavailable",
                    path=str(self.service.startup_log_path().parent),
                    error=str(error),
                ),
            )
            return
        path = self.service.startup_log_path().resolve()
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except OSError as error:
            QMessageBox.warning(
                self, self.tr("error"), self.tr("open_file_failed", error=str(error))
            )

    def show_first_run_setup(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        dialog.setWindowTitle(self.tr("first_run"))
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(self.tr("license_text")))
        accepted = QCheckBox(self.tr("license_acceptance"))
        layout.addWidget(accepted)
        path = QLineEdit()
        path.setReadOnly(True)
        choose = button(dialog, "folder", self.tr("choose_folder"))
        choose.clicked.connect(
            lambda: path.setText(QFileDialog.getExistingDirectory(dialog, self.tr("choose_folder")))
        )
        layout.addWidget(path)
        layout.addWidget(choose)
        accept = button(dialog, "save", self.tr("accept_and_continue"))
        accept.clicked.connect(
            lambda: self.complete_first_run(dialog, path.text(), accepted.isChecked())
        )
        layout.addWidget(accept)
        dialog.exec()

    def complete_first_run(self, dialog: QDialog, path: str, accepted: bool) -> None:
        if not accepted:
            QMessageBox.warning(dialog, self.tr("error"), self.tr("license_required"))
            return
        try:
            self.service.complete_setup(Path(path))
        except ValueError:
            QMessageBox.warning(dialog, self.tr("error"), self.tr("folder_missing"))
            return
        self.refresh_images()
        dialog.accept()

    def recognition(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        path = QHBoxLayout()
        self.folder = QLineEdit(str(self.service.image_directory() or ""))
        self.folder.setReadOnly(True)
        open_folder = button(page, "folder", self.tr("open_folder"))
        open_folder.clicked.connect(self.open_folder)
        path.addWidget(self.folder)
        path.addWidget(open_folder)
        layout.addLayout(path)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.photo_splitter = split
        photos = QWidget()
        left = QVBoxLayout(photos)
        actions = QHBoxLayout()
        for action, handler in (("refresh", self.refresh_images), ("delete", self.delete_image)):
            control = button(photos, action, self.tr(action))
            control.clicked.connect(handler)
            actions.addWidget(control)
        images_heading = QHBoxLayout()
        images_heading.addWidget(QLabel(self.tr("images")))
        images_heading.addWidget(self.help_button("images", "images"))
        images_heading.addStretch()
        left.addLayout(images_heading)
        left.addLayout(actions)
        pager = QHBoxLayout()
        self.image_previous = button(photos, "previous", self.tr("previous_page"))
        self.image_previous.clicked.connect(lambda: self.change_image_page(-1))
        self.image_page_label = QLabel()
        self.image_next = button(photos, "next", self.tr("next_page"))
        self.image_next.clicked.connect(lambda: self.change_image_page(1))
        pager.addWidget(self.image_previous)
        pager.addWidget(self.image_page_label)
        pager.addWidget(self.image_next)
        left.addLayout(pager)
        self.image_cards = QScrollArea()
        self.image_cards.setWidgetResizable(True)
        self.image_cards.setMinimumHeight(0)
        self.image_cards.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.image_cards_content = QWidget()
        self.image_cards_layout = QVBoxLayout(self.image_cards_content)
        self.image_cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.image_cards.setWidget(self.image_cards_content)
        self.image_cards.viewport().installEventFilter(self)
        self.image_button_group = QButtonGroup(self)
        self.image_button_group.setExclusive(True)
        self.image_card_groups = []
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_controls = QHBoxLayout()
        for action, handler in (
            ("open_image", self.open_selected_image),
            ("editor", self.edit_image),
            ("rotate", self.rotate),
        ):
            control = button(preview_panel, action, self.tr(action))
            control.clicked.connect(handler)
            preview_controls.addWidget(control)
        preview_controls.addStretch()
        fit = button(preview_panel, "fit_image", self.tr("fit_image"))
        fit.clicked.connect(self.zoom_image_to_fit)
        actual = button(preview_panel, "actual_size", self.tr("actual_size"))
        actual.clicked.connect(self.zoom_image_actual)
        preview_controls.addWidget(fit)
        preview_controls.addWidget(actual)
        preview_layout.addLayout(preview_controls)
        self.preview = PhotoPreview(self.tr("select_image"))
        self.preview.setToolTip(self.tr("preview_zoom_hint"))
        self.preview.setAccessibleName(self.tr("image_preview"))
        self.preview.setMinimumHeight(0)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        preview_layout.addWidget(self.preview, 1)
        self.image_splitter = QSplitter(Qt.Orientation.Vertical)
        self.image_splitter.setChildrenCollapsible(True)
        self.image_splitter.addWidget(self.image_cards)
        self.image_splitter.addWidget(preview_panel)
        self.image_splitter.setCollapsible(0, True)
        self.image_splitter.setCollapsible(1, True)
        self.image_splitter.setSizes([360, 480])
        self.image_splitter.setStretchFactor(0, 1)
        self.image_splitter.setStretchFactor(1, 2)
        left.addWidget(self.image_splitter, 1)
        split.addWidget(photos)
        results = QWidget()
        right = QVBoxLayout(results)
        recognition_actions = QHBoxLayout()
        self.recognition_status = QLabel(self.tr("recognition_ready"))
        self.recognition_status.setObjectName("recognitionStatus")
        self.recognition_status.setWordWrap(True)
        recognition_actions.addWidget(self.recognition_status, 1)
        self.retry_button = button(results, "retry", self.tr("retry_recognition"))
        self.retry_button.setEnabled(False)
        self.retry_button.clicked.connect(self.retry_recognition)
        recognition_actions.addWidget(self.retry_button)
        self.cancel_recognition_button = button(results, "cancel", self.tr("cancel_recognition"))
        self.cancel_recognition_button.setEnabled(False)
        self.cancel_recognition_button.clicked.connect(self.cancel_recognition)
        recognition_actions.addWidget(self.cancel_recognition_button)
        right.addLayout(recognition_actions)
        ocr_heading = QHBoxLayout()
        ocr_heading.addWidget(QLabel(self.tr("ocr")))
        ocr_heading.addWidget(self.help_button("ocr", "ocr"))
        ocr_heading.addStretch()
        right.addLayout(ocr_heading)
        ocrbar = QHBoxLayout()
        self.ocr_language = QComboBox()
        self.ocr_language.addItem("English", "eng")
        self.ocr_language.addItem("Українська", "ukr")
        self.ocr_language.addItem("Polski", "pol")
        ocrbar.addWidget(QLabel(self.tr("ocr_language")))
        ocrbar.addWidget(self.ocr_language)
        right.addLayout(ocrbar)
        self.ocr_result = QTextEdit(self.tr("ocr_empty"))
        self.ocr_result.setObjectName("recognitionResult")
        self.bind_result_menu(self.ocr_result)
        right.addWidget(self.ocr_result, 1)
        barcode_heading = QHBoxLayout()
        barcode_heading.addWidget(QLabel(self.tr("barcodes")))
        barcode_heading.addWidget(self.help_button("barcode-ai", "barcodes"))
        barcode_heading.addStretch()
        right.addLayout(barcode_heading)
        self.barcode_result = QTextEdit(self.tr("barcode_empty"))
        self.barcode_result.setObjectName("recognitionResult")
        self.barcode_result.setReadOnly(True)
        self.bind_result_menu(self.barcode_result)
        right.addWidget(self.barcode_result, 1)
        ai_heading = QHBoxLayout()
        ai_heading.addWidget(QLabel(self.tr("ai")))
        ai_heading.addWidget(self.help_button("barcode-ai", "ai"))
        ai_heading.addStretch()
        right.addLayout(ai_heading)
        ai_bar = QHBoxLayout()
        self.agent_select = QComboBox()
        self.agent_select.currentIndexChanged.connect(self.agent_changed)
        self.ai_button = button(results, "ocr", self.tr("run_ai"))
        self.ai_button.clicked.connect(self.run_ai)
        ai_bar.addWidget(self.agent_select, 1)
        ai_bar.addWidget(self.ai_button)
        right.addLayout(ai_bar)
        self.ai_result = QTextEdit(self.tr("ai_empty"))
        self.ai_result.setObjectName("recognitionResult")
        self.ai_result.setReadOnly(True)
        self.bind_result_menu(self.ai_result)
        right.addWidget(self.ai_result, 1)
        split.addWidget(results)
        split.setSizes([1050, 450])
        split.setStretchFactor(0, 7)
        split.setStretchFactor(1, 3)
        layout.addWidget(split)
        return page

    def camera_scan(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        self.camera_selector = QComboBox(page)
        self.camera_refresh = button(page, "refresh", self.tr("camera_refresh"))
        self.camera_refresh.clicked.connect(self.refresh_camera_devices)
        self.camera_start = button(page, "camera", self.tr("camera_start"))
        self.camera_start.clicked.connect(self.start_camera)
        self.camera_stop_button = button(page, "stop", self.tr("camera_stop"))
        self.camera_stop_button.clicked.connect(self.stop_camera)
        self.camera_capture_button = button(page, "capture", self.tr("camera_capture"))
        self.camera_capture_button.clicked.connect(self.capture_camera_frame)
        controls.addWidget(QLabel(self.tr("camera")))
        controls.addWidget(self.camera_selector, 1)
        controls.addWidget(self.camera_refresh)
        controls.addWidget(self.camera_start)
        controls.addWidget(self.camera_stop_button)
        controls.addWidget(self.camera_capture_button)
        layout.addLayout(controls)
        self.camera_status = QLabel(self.tr("camera_unavailable"), page)
        self.camera_status.setWordWrap(True)
        layout.addWidget(self.camera_status)
        self.camera_view = QVideoWidget(page)
        self.camera_view.setMinimumHeight(360)
        layout.addWidget(self.camera_view, 1)
        layout.addWidget(QLabel(self.tr("camera_result"), page))
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
            self.tr("camera_select") if available else self.tr("camera_unavailable")
        )

    def start_camera(self) -> None:
        device = self.camera_selector.currentData()
        if device is None:
            self.camera_status.setText(self.tr("camera_unavailable"))
            return
        self.stop_camera(update_status=False)
        try:
            self.camera = QCamera(device, self)
            self.camera_capture = QImageCapture(self)
            self.camera_capture.imageSaved.connect(self.camera_image_saved)
            self.camera_capture.errorOccurred.connect(
                lambda *_args: self.camera_status.setText(
                    self.tr("camera_error", error=str(_args[-1]))
                )
            )
            self.camera_session = QMediaCaptureSession(self)
            self.camera_session.setCamera(self.camera)
            self.camera_session.setVideoOutput(self.camera_view)
            self.camera_session.setImageCapture(self.camera_capture)
            self.camera.start()
        except RuntimeError as error:
            self.stop_camera()
            self.camera_status.setText(self.tr("camera_error", error=str(error)))
            return
        self.camera_start.setEnabled(False)
        self.camera_stop_button.setEnabled(True)
        self.camera_capture_button.setEnabled(True)
        self.camera_status.setText(self.tr("camera_ready"))

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
                    self.tr("camera_stopped") if available else self.tr("camera_unavailable")
                )

    def on_tab_changed(self, _index: int) -> None:
        if self.tabs.currentWidget() is not self.camera_tab:
            self.stop_camera()

    def capture_camera_frame(self) -> None:
        if self.camera_capture is None:
            self.camera_status.setText(self.tr("camera_unavailable"))
            return
        destination = (
            Path(tempfile.gettempdir())
            / f"advanced-serial-vision-scan-{datetime.now().strftime('%Y%m%d%H%M%S%f')}.jpg"
        )
        self.camera_status.setText(self.tr("camera_capturing"))
        self.camera_capture.captureToFile(str(destination))

    def camera_image_saved(self, _request_id: int, filename: str) -> None:
        path = Path(filename)
        try:
            result = BarcodeRecognizer(
                self.tr("barcode_module_unavailable"), self.service.recognition_options()
            ).recognize(path)
            self.camera_result.setPlainText(result or self.tr("camera_result_empty"))
            self.camera_status.setText(self.tr("camera_ready"))
        except RuntimeError as error:
            self.camera_status.setText(self.tr("camera_error", error=str(error)))
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def settings(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(
            self.help_button("settings", "settings"), alignment=Qt.AlignmentFlag.AlignRight
        )
        interface = QGroupBox(self.tr("interface_settings"))
        interface_form = QFormLayout(interface)
        self.language = QComboBox()
        for code, name in (("uk", "Українська"), ("en", "English"), ("pl", "Polski")):
            self.language.addItem(name, code)
        self.language.setCurrentIndex(SUPPORTED_LOCALES.index(self.locale))
        interface_form.addRow(self.tr("language"), self.language)
        layout.addWidget(interface)

        folder_group = QGroupBox(self.tr("folder_settings"))
        folder_form = QFormLayout(folder_group)
        self.settings_folder_path = QLineEdit(str(self.service.image_directory() or ""))
        self.settings_folder_path.setReadOnly(True)
        choose = button(folder_group, "folder", self.tr("choose_folder"))
        choose.clicked.connect(self.choose_folder)
        folder_form.addRow(self.tr("image_folder"), self.settings_folder_path)
        folder_form.addRow(choose)
        layout.addWidget(folder_group)

        appearance = QGroupBox(self.tr("appearance_settings"))
        appearance_form = QFormLayout(appearance)
        self.theme_choice = QComboBox()
        self.theme_choice.addItem(self.tr("theme_system"), "system")
        self.theme_choice.addItem(self.tr("theme_light"), "light")
        self.theme_choice.addItem(self.tr("theme_dark"), "dark")
        self.theme_choice.setCurrentIndex(max(0, self.theme_choice.findData(self.service.theme())))
        self.icon_style_choice = QComboBox()
        self.icon_style_choice.addItem(self.tr("icon_style_system"), "system")
        self.icon_style_choice.addItem(self.tr("icon_style_modern"), "modern")
        self.icon_style_choice.addItem(self.tr("icon_style_classic"), "classic")
        self.icon_style_choice.addItem(self.tr("icon_style_windows98"), "windows98")
        self.icon_style_choice.addItem(self.tr("icon_style_ubuntu22"), "ubuntu22")
        self.icon_style_choice.setCurrentIndex(
            max(0, self.icon_style_choice.findData(self.service.icon_style()))
        )
        appearance_form.addRow(self.tr("theme"), self.theme_choice)
        appearance_form.addRow(self.tr("icon_style"), self.icon_style_choice)
        layout.addWidget(appearance)

        recognition_group = QGroupBox(self.tr("recognition_strategies"))
        recognition_form = QFormLayout(recognition_group)
        options = self.service.recognition_options()
        original_info = QLabel(self.tr("recognition_original_info"))
        original_info.setWordWrap(True)
        recognition_form.addRow(original_info)
        self.recognition_rotate = QCheckBox(self.tr("recognition_rotate"))
        self.recognition_rotate.setChecked(options.rotate)
        recognition_form.addRow(self.recognition_rotate)
        self.recognition_enhance = QCheckBox(self.tr("recognition_enhance"))
        self.recognition_enhance.setChecked(options.enhance)
        recognition_form.addRow(self.recognition_enhance)
        layout.addWidget(recognition_group)

        api = QGroupBox(self.tr("api_integrations"))
        api_form = QFormLayout(api)
        self.api_enabled = QCheckBox(self.tr("api_enabled"))
        self.api_enabled.setChecked(self.service.api_enabled())
        self.api_port = QLineEdit(str(self.service.api_port()))
        api_form.addRow(self.api_enabled)
        api_form.addRow(self.tr("api_port"), self.api_port)
        layout.addWidget(api)

        profiles = QGroupBox(self.tr("ai_profiles"))
        agent = QVBoxLayout(profiles)
        self.agent_profiles = self.table(
            [self.tr("profile_name"), self.tr("provider"), self.tr("model")]
        )
        self.agent_profiles.cellDoubleClicked.connect(lambda *_: self.edit_selected_agent())
        agent.addWidget(self.agent_profiles)
        actions = QHBoxLayout()
        add = button(profiles, "save", self.tr("add_profile"))
        add.clicked.connect(self.add_agent)
        edit = button(profiles, "edit", self.tr("edit_profile"))
        edit.clicked.connect(self.edit_selected_agent)
        remove = button(profiles, "delete", self.tr("remove_profile"))
        remove.clicked.connect(self.delete_selected_agent)
        actions.addWidget(add)
        actions.addWidget(edit)
        actions.addWidget(remove)
        actions.addStretch()
        agent.addLayout(actions)
        layout.addWidget(profiles)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.addWidget(scroll, 1)
        save_bar = QHBoxLayout()
        self.settings_status = QLabel(self.tr("settings_saved"))
        self.settings_status.setObjectName("settingsStatus")
        save_bar.addWidget(self.settings_status, 1)
        self.settings_save = button(container, "save", self.tr("save_settings"))
        self.settings_save.setEnabled(False)
        self.settings_save.clicked.connect(self.save_all_settings)
        save_bar.addWidget(self.settings_save)
        outer.addLayout(save_bar)
        self.settings_page = container
        self._settings_saved_values = self.settings_values()
        for control in (self.language, self.theme_choice, self.icon_style_choice):
            control.currentIndexChanged.connect(self.settings_changed)
        for control in (self.recognition_rotate, self.recognition_enhance, self.api_enabled):
            control.toggled.connect(self.settings_changed)
        for control in (self.settings_folder_path, self.api_port):
            control.textChanged.connect(self.settings_changed)
        return container

    def api_integrations(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        keys_page = QWidget()
        keys_layout = QVBoxLayout(keys_page)
        self.api_keys_table = self.table(
            [
                self.tr("profile_name"),
                self.tr("note"),
                self.tr("api_key_prefix"),
                self.tr("api_rate"),
                self.tr("expires_at"),
                self.tr("api_status"),
            ]
        )
        keys_layout.addWidget(self.api_keys_table)
        actions = QHBoxLayout()
        issue = button(keys_page, "save", self.tr("issue_api_key"))
        issue.clicked.connect(self.issue_api_key)
        revoke = button(keys_page, "delete", self.tr("revoke_api_key"))
        revoke.clicked.connect(self.revoke_selected_api_key)
        refresh = button(keys_page, "refresh", self.tr("refresh"))
        refresh.clicked.connect(self.refresh_api_integration)
        actions.addWidget(issue)
        actions.addWidget(revoke)
        actions.addWidget(refresh)
        actions.addStretch()
        keys_layout.addLayout(actions)
        tabs.addTab(keys_page, self.tr("api_keys"))
        audit_page = QWidget()
        audit_layout = QVBoxLayout(audit_page)
        self.api_audit_table = self.table(
            [
                self.tr("date_time"),
                self.tr("profile_name"),
                self.tr("method"),
                self.tr("path"),
                self.tr("status"),
            ]
        )
        audit_layout.addWidget(self.api_audit_table)
        audit_refresh = button(audit_page, "refresh", self.tr("refresh"))
        audit_refresh.clicked.connect(self.refresh_api_integration)
        audit_layout.addWidget(audit_refresh)
        tabs.addTab(audit_page, self.tr("api_audit"))
        return page

    def equipment(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setSpecialValueText("—")
        self.date_from.setDate(QDate(2000, 1, 1))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setSpecialValueText("—")
        self.date_to.setDate(QDate(2000, 1, 1))
        self.model_filter = QComboBox()
        self.operation_filter = QComboBox()
        self.operation_filter.addItem(self.tr("operation"), "")
        self.operation_filter.addItem(self.tr("receipt"), "receipt")
        self.operation_filter.addItem(self.tr("issue"), "issue")
        self.type_filter = QComboBox()
        self.type_filter.addItem(self.tr("all_types"), "")
        self.type_filter.addItem(self.tr("modem"), "modem")
        self.type_filter.addItem(self.tr("tuner"), "tuner")
        self.service_filter = QComboBox()
        self.service_filter.addItem(self.tr("all_services"), "")
        self.service_filter.addItem(self.tr("internet"), "internet")
        self.service_filter.addItem(self.tr("television"), "television")
        self.device_search = QLineEdit()
        self.device_search.setPlaceholderText(self.tr("search"))
        self.device_search.returnPressed.connect(self.refresh_equipment)
        filters = QGridLayout()
        filter_fields = (
            ("date_from_label", self.date_from),
            ("date_to_label", self.date_to),
            ("model", self.model_filter),
            ("operation", self.operation_filter),
            ("type", self.type_filter),
            ("service", self.service_filter),
        )
        for index, (label_key, control) in enumerate(filter_fields):
            row, column = divmod(index, 3)
            label = QLabel(self.tr(label_key))
            label.setBuddy(control)
            control.setAccessibleName(self.tr(label_key))
            filters.addWidget(label, row * 2, column)
            filters.addWidget(control, row * 2 + 1, column)
        search_label = QLabel(self.tr("search"))
        search_label.setBuddy(self.device_search)
        self.device_search.setAccessibleName(self.tr("search"))
        filters.addWidget(search_label, 4, 0)
        filters.addWidget(self.device_search, 5, 0, 1, 2)
        filter_actions = QHBoxLayout()
        refresh = button(page, "refresh", self.tr("refresh"))
        refresh.clicked.connect(self.refresh_equipment)
        export = button(page, "export", self.tr("export"))
        export.clicked.connect(self.export_equipment)
        filter_actions.addWidget(refresh)
        filter_actions.addWidget(export)
        filter_actions.addWidget(self.help_button("search-export", "equipment"))
        filters.addLayout(filter_actions, 5, 2)
        for column in range(3):
            filters.setColumnStretch(column, 1)
        layout.addLayout(filters)
        add = button(page, "save", self.tr("add_record"))
        add.clicked.connect(lambda: self.open_equipment_dialog(""))
        layout.addWidget(add)
        self.devices_table = self.table(
            [
                self.tr(key)
                for key in (
                    "date_time",
                    "contract",
                    "operation",
                    "recognized_text",
                    "model",
                    "type",
                    "service",
                    "images",
                    "actions",
                )
            ]
        )
        header = self.devices_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        self.devices_table.cellDoubleClicked.connect(lambda row, _: self.edit_equipment(row))
        layout.addWidget(self.devices_table)
        equipment_pager = QHBoxLayout()
        self.equipment_previous = button(page, "previous", self.tr("previous_page"))
        self.equipment_previous.clicked.connect(lambda: self.change_equipment_page(-1))
        self.equipment_page_label = QLabel()
        self.equipment_next = button(page, "next", self.tr("next_page"))
        self.equipment_next.clicked.connect(lambda: self.change_equipment_page(1))
        equipment_pager.addWidget(self.equipment_previous)
        equipment_pager.addWidget(self.equipment_page_label)
        equipment_pager.addWidget(self.equipment_next)
        layout.addLayout(equipment_pager)
        return page

    def models(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        add = button(page, "save", self.tr("add_model"))
        add.clicked.connect(self.add_model)
        import_button = button(page, "open", self.tr("import_models"))
        import_button.clicked.connect(self.import_models)
        controls.addWidget(add)
        controls.addWidget(import_button)
        controls.addWidget(self.help_button("models", "models"))
        controls.addStretch()
        layout.addLayout(controls)
        self.models_table = self.table(
            [
                self.tr("model"),
                self.tr("type"),
                self.tr("service"),
                self.tr("usage_count"),
                self.tr("actions"),
            ]
        )
        self.models_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.models_table.setSortingEnabled(True)
        self.models_table.cellDoubleClicked.connect(lambda row, _: self.edit_model(row))
        layout.addWidget(self.models_table)
        return page

    def statistics(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(
            self.help_button("statistics", "statistics"), alignment=Qt.AlignmentFlag.AlignRight
        )
        self.statistics_mode = QComboBox()
        self.statistics_mode.addItem(self.tr("day"), "day")
        self.statistics_mode.addItem(self.tr("month"), "month")
        self.statistics_mode.setCurrentIndex(1)
        self.statistics_mode.currentIndexChanged.connect(self.refresh_statistics)
        layout.addWidget(self.statistics_mode)
        self.statistics_table = self.table(
            [self.tr("date_time"), self.tr("receipt"), self.tr("issue"), self.tr("total")]
        )
        layout.addWidget(self.statistics_table)
        self.operations_chart = QChartView()
        self.services_chart = QChartView()
        self.models_chart = QChartView()
        for chart in (self.operations_chart, self.services_chart, self.models_chart):
            chart.setMinimumHeight(190)
            layout.addWidget(chart)
        return page

    def period_label(self, period: str) -> str:
        locale = QLocale(self.locale)
        if len(period) == 7:
            year, month = period.split("-")
            return f"{locale.standaloneMonthName(int(month))} {year}"
        return locale.toString(
            QDate.fromString(period, "yyyy-MM-dd"), QLocale.FormatType.ShortFormat
        )

    def make_bar_chart(
        self, title: str, categories: list[str], series_values: list[tuple[str, list[int]]]
    ) -> QChart:
        series = QBarSeries()
        maximum = 1
        for label, values in series_values:
            bar_set = QBarSet(label)
            bar_set.append(values)
            series.append(bar_set)
            maximum = max([maximum, *values])
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(title)
        chart.legend().setVisible(len(series_values) > 1)
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_y = QValueAxis()
        axis_y.setRange(0, maximum)
        axis_y.setLabelFormat("%d")
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
        return chart

    def refresh_images(self) -> None:
        self.catalog = ImageCatalog(self.service.image_directory())
        self.folder.setText(str(self.service.image_directory() or ""))
        while self.image_cards_layout.count():
            item = self.image_cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.image_button_group.deleteLater()
        self.image_button_group = QButtonGroup(self)
        self.image_button_group.setExclusive(True)
        images, metadata = self.catalog.page(self.image_page)
        self.image_page = int(metadata["page"])
        self.image_page_label.setText(str(self.image_page) + "/" + str(metadata["pages"]))
        self.image_previous.setEnabled(self.image_page > 1)
        self.image_next.setEnabled(bool(metadata["has_more"]))
        if self.selected_image is not None and self.selected_image not in {
            image.path for image in images
        }:
            self.clear_image_selection()
        self.image_card_groups = []
        self._image_buttons = {}
        groups: dict[str, list] = {}
        for image in images:
            label = datetime.fromtimestamp(image.path.stat().st_mtime).strftime("%Y-%m-%d")
            groups.setdefault(label, []).append(image)
        for date_label, day_images in groups.items():
            heading = QLabel(self.period_label(date_label))
            heading.setObjectName("imageDateHeading")
            self.image_cards_layout.addWidget(heading)
            cards = QWidget()
            grid = QGridLayout(cards)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(8)
            day_cards = []
            for index, image in enumerate(day_images):
                card = QToolButton(cards)
                card.setCheckable(True)
                card.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                card.setText(image.name)
                card.setToolTip(image.name)
                card.setAccessibleName(image.name)
                pixmap = QPixmap(str(image.path))
                card.setIcon(QIcon(pixmap))
                card.setIconSize(QSize(150, 95))
                card.setMinimumWidth(165)
                card.setMaximumWidth(205)
                card.setMinimumHeight(130)
                card.setChecked(image.path == self.selected_image)
                card.clicked.connect(
                    lambda _checked=False, path=image.path: self.select_image_path(path)
                )
                self.image_button_group.addButton(card)
                day_cards.append(card)
                self._image_buttons[image.path] = card
                grid.addWidget(card, index // 4, index % 4)
            self.image_card_groups.append((grid, day_cards))
            self.image_cards_layout.addWidget(cards)
        self.image_cards_layout.addStretch()
        self.relayout_image_cards()

    def relayout_image_cards(self) -> None:
        columns = max(1, (self.image_cards.viewport().width() - 16) // 173)
        for grid, cards in self.image_card_groups:
            for index, card in enumerate(cards):
                grid.addWidget(card, index // columns, index % columns)

    def change_image_page(self, offset: int) -> None:
        self.image_page = max(1, self.image_page + offset)
        self.refresh_images()

    def select_image_path(self, image_path: Path) -> None:
        self.invalidate_ai_result()
        if not self.preview.set_image(image_path):
            self.clear_image_selection()
            QMessageBox.warning(
                self, self.tr("error"), self.tr("open_file_failed", error=str(image_path))
            )
            return
        self.selected_image = image_path
        card = self._image_buttons.get(image_path)
        if card is not None:
            card.setChecked(True)
        self.start_recognition()

    def clear_image_selection(self) -> None:
        self.invalidate_ai_result()
        worker = getattr(self, "recognition_worker", None)
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
        self.recognition_generation += 1
        self.selected_image = None
        self.preview.set_image(None)
        self.ocr_result.setPlainText(self.tr("ocr_empty"))
        self.barcode_result.setPlainText(self.tr("barcode_empty"))
        self.ai_result.setPlainText(self.tr("ai_empty"))
        self.recognition_status.setText(self.tr("recognition_ready"))
        self.set_recognition_busy(False)

    def start_recognition(self) -> None:
        if self.selected_image is None:
            return
        old_worker = getattr(self, "recognition_worker", None)
        if old_worker is not None and old_worker.isRunning():
            old_worker.requestInterruption()
        self.recognition_generation += 1
        generation = self.recognition_generation
        self.set_recognition_busy(True)
        self.recognition_status.setText(self.tr("recognition_step_ocr"))
        self.ocr_result.setPlainText(self.tr("recognizing"))
        self.barcode_result.setPlainText(self.tr("recognizing"))
        worker = RecognitionWorker(
            self.selected_image,
            self.ocr_language.currentData(),
            self.tr("barcode_ocr_fallback"),
            self.tr("barcode_module_unavailable"),
            self.service.recognition_options(),
            self,
        )
        self.recognition_worker = worker
        self._recognition_workers.add(worker)
        worker.stage.connect(
            lambda stage, current=generation: self.recognition_stage(current, stage)
        )
        worker.completed.connect(
            lambda path,
            ocr_text,
            barcode_text,
            error,
            current=generation: self.recognition_finished(
                current, path, ocr_text, barcode_text, error
            )
        )
        worker.cancelled.connect(
            lambda _path, current=generation: self.recognition_cancelled(current)
        )
        worker.finished.connect(lambda current=worker: self.recognition_worker_finished(current))
        worker.start()

    def recognition_worker_finished(self, worker: RecognitionWorker) -> None:
        self._recognition_workers.discard(worker)
        if getattr(self, "recognition_worker", None) is worker:
            self.recognition_worker = None
        worker.deleteLater()

    def recognition_stage(self, generation: int, stage: str) -> None:
        worker = getattr(self, "recognition_worker", None)
        if generation == self.recognition_generation and (
            worker is None or not worker.isInterruptionRequested()
        ):
            self.recognition_status.setText(
                self.tr("recognition_step_ocr" if stage == "ocr" else "recognition_step_barcode")
            )

    def cancel_recognition(self) -> None:
        worker = getattr(self, "recognition_worker", None)
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            self.recognition_status.setText(self.tr("recognition_cancelling"))
            self.cancel_recognition_button.setEnabled(False)

    def recognition_cancelled(self, generation: int) -> None:
        if generation != self.recognition_generation:
            return
        self.ocr_result.setPlainText(self.tr("recognition_cancelled"))
        self.barcode_result.setPlainText(self.tr("recognition_cancelled"))
        self.recognition_status.setText(self.tr("recognition_cancelled"))
        self.set_recognition_busy(False)

    def set_recognition_busy(self, busy: bool) -> None:
        self._recognition_busy = busy
        for widget in (self.ocr_language, self.ocr_result, self.barcode_result, self.agent_select):
            widget.setDisabled(busy)
        self.agent_select.setDisabled(busy or self._ai_busy)
        self.retry_button.setEnabled(not busy and self.selected_image is not None)
        self.cancel_recognition_button.setEnabled(busy)
        self.agent_changed()

    def recognition_finished(
        self, generation: int, image_path: str, ocr_text: str, barcode_text: str, error: str
    ) -> None:
        if (
            generation != self.recognition_generation
            or self.selected_image is None
            or str(self.selected_image) != image_path
        ):
            return
        self.ocr_result.setPlainText(ocr_text or self.tr("ocr_empty"))
        self.barcode_result.setPlainText(barcode_text or self.tr("barcodes_not_found"))
        self.recognition_status.setText(self.tr("recognition_finished"))
        self.set_recognition_busy(False)

    def required(self) -> bool:
        if self.selected_image is None:
            QMessageBox.warning(self, self.tr("error"), self.tr("no_image"))
            return False
        return True

    def open_selected_image(self) -> None:
        if self.required():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.selected_image)))

    def edit_image(self) -> None:
        if not self.required():
            return
        existing = getattr(self, "image_editor", None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        try:
            dialog = ImageEditorDialog(
                self.service,
                self.selected_image,
                self.locale,
                str(self.ocr_language.currentData()),
                RecognitionWorker,
                AiRecognitionWorker,
                self,
            )
        except (OSError, ValueError) as error:
            QMessageBox.warning(
                self, self.tr("error"), self.tr("open_file_failed", error=str(error))
            )
            return
        self.image_editor = dialog
        dialog.destroyed.connect(
            lambda: setattr(self, "image_editor", None) if self.image_editor is dialog else None
        )
        dialog.show()

    def rotate(self) -> None:
        if self.required():
            try:
                self.catalog.rotate_clockwise(self.selected_image)
            except (OSError, ValueError) as error:
                self.error(error_message(self.locale, error))
                return
            self.select_image_path(self.selected_image)

    def delete_image(self) -> None:
        if (
            self.required()
            and QMessageBox.question(self, self.tr("confirm"), self.tr("delete_image"))
            == QMessageBox.StandardButton.Yes
        ):
            try:
                self.catalog.delete(self.selected_image)
            except (OSError, ValueError) as error:
                self.error(error_message(self.locale, error))
                return
            self.clear_image_selection()
            self.refresh_images()

    def zoom_image_to_fit(self) -> None:
        self.preview.zoom_to_fit()

    def zoom_image_actual(self) -> None:
        self.preview.zoom_actual()

    def retry_recognition(self) -> None:
        if self.required() and (
            not getattr(self, "recognition_worker", None) or not self.recognition_worker.isRunning()
        ):
            self.start_recognition()

    def run_ai(self) -> None:
        if not self.required():
            return
        agent_id = self.agent_select.currentData()
        if not agent_id:
            QMessageBox.warning(self, self.tr("error"), self.tr("profile_required"))
            return
        if getattr(self, "ai_worker", None) and self.ai_worker.isRunning():
            return
        self.set_ai_busy(True)
        self.ai_result.setPlainText(self.tr("ai_recognizing"))
        generation = self._ai_generation
        image_path = self.selected_image
        self.ai_worker = AiRecognitionWorker(self.service, agent_id, self.selected_image, self)
        self.ai_worker.completed.connect(
            lambda text: self.ai_finished(text, generation, image_path, agent_id)
        )
        self.ai_worker.failed.connect(
            lambda error: self.ai_failed(error, generation, image_path, agent_id)
        )
        self.ai_worker.finished.connect(lambda: self.set_ai_busy(False))
        self.ai_worker.start()

    def invalidate_ai_result(self) -> None:
        self._ai_generation += 1
        self.ai_result.setPlainText(self.tr("ai_empty"))

    def set_ai_busy(self, busy: bool) -> None:
        self._ai_busy = busy
        self.agent_select.setDisabled(busy or self._recognition_busy)
        self.agent_changed()

    def ai_finished(self, text: str, generation: int, image_path: Path, agent_id: str) -> None:
        if (
            not self._closing
            and generation == self._ai_generation
            and image_path == self.selected_image
            and agent_id == self.agent_select.currentData()
        ):
            self.ai_result.setPlainText(text)

    def ai_failed(self, error: str, generation: int, image_path: Path, agent_id: str) -> None:
        if (
            not self._closing
            and generation == self._ai_generation
            and image_path == self.selected_image
            and agent_id == self.agent_select.currentData()
        ):
            self.ai_result.setPlainText(error_message(self.locale, error))

    def settings_values(self) -> SettingsValues:
        return SettingsValues(
            locale=str(self.language.currentData()),
            image_directory=self.settings_folder_path.text(),
            theme=str(self.theme_choice.currentData()),
            icon_style=str(self.icon_style_choice.currentData()),
            rotate=self.recognition_rotate.isChecked(),
            enhance=self.recognition_enhance.isChecked(),
            api_enabled=self.api_enabled.isChecked(),
            api_port=self.api_port.text().strip(),
        )

    def settings_changed(self, *_args) -> None:
        dirty = self.settings_values() != self._settings_saved_values
        self.settings_save.setEnabled(dirty)
        self.settings_status.setText(self.tr("settings_unsaved" if dirty else "settings_saved"))
        self.settings_status.setProperty("state", "dirty" if dirty else "saved")
        self.settings_status.style().unpolish(self.settings_status)
        self.settings_status.style().polish(self.settings_status)
        if hasattr(self, "tabs"):
            index = self.tabs.indexOf(self.settings_page)
            if index >= 0:
                self.tabs.setTabText(index, self.tr("settings") + (" *" if dirty else ""))

    def save_all_settings(self) -> None:
        current = self.settings_values()
        previous = self._settings_saved_values
        folder = Path(current.image_directory)
        folder_changed = current.image_directory != previous.image_directory
        if folder_changed and not folder.is_dir():
            self.settings_status.setText(self.tr("folder_missing"))
            return
        api_changed = (current.api_enabled, current.api_port) != (
            previous.api_enabled,
            previous.api_port,
        )
        if api_changed:
            try:
                port = int(current.api_port)
            except ValueError:
                self.settings_status.setText(self.tr("api_port_invalid"))
                self.api_port.setFocus()
                return
            if not 1024 <= port <= 65535:
                self.settings_status.setText(self.tr("api_port_invalid"))
                self.api_port.setFocus()
                return
            try:
                self.service.save_api_settings(current.api_enabled, port)
                self.local_api.restart()
            except (ValueError, OSError) as error:
                self.service.save_api_settings(previous.api_enabled, int(previous.api_port))
                try:
                    self.local_api.restart()
                except OSError:
                    pass
                self.settings_status.setText(self.tr("api_start_failed", error=str(error)))
                return
            self.api_integration_tab.setEnabled(current.api_enabled)
        if folder_changed:
            self.service.save_settings(folder)
            self.image_page = 1
            self.clear_image_selection()
            self.refresh_images()
        if (current.rotate, current.enhance) != (previous.rotate, previous.enhance):
            self.service.save_recognition_options(
                RecognitionOptions(current.rotate, current.enhance)
            )
        if (current.theme, current.icon_style) != (previous.theme, previous.icon_style):
            self.service.save_appearance(current.theme, current.icon_style)
            app = QApplication.instance()
            if app is not None:
                apply_button_icons(current.icon_style)
                self.tabs.setIconSize(icon_size(current.icon_style))
                for index, name in enumerate(
                    (
                        "recognition",
                        "equipment",
                        "models",
                        "statistics",
                        "scan",
                        "api_integrations",
                        "settings",
                    )
                ):
                    self.tabs.setTabIcon(index, self.tab_icon(name))
                apply_theme(app, current.theme)
                self.refresh_equipment()
        if current.locale != previous.locale:
            self.service.save_locale(current.locale)
        self._settings_saved_values = current
        self.settings_changed()
        if current.locale != previous.locale:
            self.settings_status.setText(self.tr("restart_language"))

    def refresh_api_integration(self) -> None:
        if not hasattr(self, "api_keys_table"):
            return
        keys = self.service.api_keys()
        self.api_keys_table.setRowCount(len(keys))
        for row, key in enumerate(keys):
            status = self.tr("api_revoked") if key["revoked_at"] else self.tr("api_active")
            self.fill(
                self.api_keys_table,
                row,
                [
                    key["name"],
                    key["note"],
                    key["token_prefix"],
                    self.rate_label(int(key["min_interval_ms"])),
                    key["expires_at"] or self.tr("never"),
                    status,
                ],
            )
            self.api_keys_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, key["id"])
        audit = self.service.api_audit()
        self.api_audit_table.setRowCount(len(audit))
        for row, entry in enumerate(audit):
            self.fill(
                self.api_audit_table,
                row,
                [
                    self.service.display_time(entry["requested_at"]),
                    entry["key_name"] or "—",
                    entry["method"],
                    entry["path"],
                    entry["status"],
                ],
            )

    def rate_label(self, value: int) -> str:
        return {
            200: self.tr("api_rate_5"),
            500: self.tr("api_rate_2"),
            1000: self.tr("api_rate_1"),
            2000: self.tr("api_rate_half"),
        }[value]

    def issue_api_key(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("issue_api_key"))
        form = QFormLayout(dialog)
        name = QLineEdit()
        note = QLineEdit()
        rate = QComboBox()
        [
            rate.addItem(label, value)
            for label, value in (
                (self.tr("api_rate_5"), 200),
                (self.tr("api_rate_2"), 500),
                (self.tr("api_rate_1"), 1000),
                (self.tr("api_rate_half"), 2000),
            )
        ]
        expires = QCheckBox(self.tr("api_key_expiry"))
        expiry = QDateTimeEdit(QDateTime.currentDateTime().addDays(30))
        expiry.setCalendarPopup(True)
        expiry.setEnabled(False)
        expires.toggled.connect(expiry.setEnabled)
        form.addRow(self.tr("profile_name"), name)
        form.addRow(self.tr("note"), note)
        form.addRow(self.tr("api_rate"), rate)
        form.addRow(expires)
        form.addRow(self.tr("expires_at"), expiry)
        create = button(dialog, "save", self.tr("issue_api_key"))
        create.clicked.connect(dialog.accept)
        form.addRow(create)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            token = self.service.issue_api_key(
                name.text(),
                note.text(),
                expiry.dateTime().toString(Qt.DateFormat.ISODate) if expires.isChecked() else None,
                int(rate.currentData()),
            )
        except ValueError as error:
            QMessageBox.warning(self, self.tr("error"), self.tr(str(error)))
            return
        result = QDialog(self)
        result.setWindowTitle(self.tr("api_key_created"))
        result_form = QVBoxLayout(result)
        result_form.addWidget(QLabel(self.tr("api_key_once")))
        value = QTextEdit(token)
        value.setReadOnly(True)
        result_form.addWidget(value)
        copy = button(result, "copy", self.tr("copy"))
        copy.clicked.connect(lambda: QApplication.clipboard().setText(token))
        result_form.addWidget(copy)
        result.exec()
        self.refresh_api_integration()

    def revoke_selected_api_key(self) -> None:
        item = self.api_keys_table.item(self.api_keys_table.currentRow(), 0)
        if (
            item
            and QMessageBox.question(self, self.tr("confirm"), self.tr("revoke_api_key_confirm"))
            == QMessageBox.StandardButton.Yes
        ):
            self.service.revoke_api_key(item.data(Qt.ItemDataRole.UserRole))
            self.refresh_api_integration()

    def refresh_agents(self) -> None:
        selected = self.agent_select.currentData() if hasattr(self, "agent_select") else ""
        self.agents = self.service.ai_agents()
        self.agent_select.clear()
        self.agent_select.addItem(self.tr("no_profiles"), "")
        for agent in self.agents:
            self.agent_select.addItem(agent["name"], agent["id"])
        index = self.agent_select.findData(selected)
        self.agent_select.setCurrentIndex(index if index >= 0 else 0)
        if hasattr(self, "agent_profiles"):
            self.refresh_agent_profiles()

    def agent_changed(self) -> None:
        enabled = (
            not self._recognition_busy
            and self.selected_image is not None
            and bool(self.agent_select.currentData())
        )
        self.ai_result.setDisabled(not enabled)
        self.ai_button.setDisabled(not enabled or self._ai_busy)

    def refresh_agent_profiles(self) -> None:
        self.agent_profiles.setRowCount(len(self.agents))
        for row, agent in enumerate(self.agents):
            for column, value in enumerate((agent["name"], agent["provider"], agent["model"])):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, agent["id"])
                self.agent_profiles.setItem(row, column, item)

    def selected_agent_id(self) -> str | None:
        row = self.agent_profiles.currentRow()
        item = self.agent_profiles.item(row, 0) if row >= 0 else None
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def add_agent(self) -> None:
        self.edit_agent_dialog()

    def edit_selected_agent(self) -> None:
        agent_id = self.selected_agent_id()
        agent = next((row for row in self.agents if row["id"] == agent_id), None)
        if agent is None:
            QMessageBox.warning(self, self.tr("error"), self.tr("profile_required"))
            return
        self.edit_agent_dialog(agent)

    def delete_selected_agent(self) -> None:
        agent_id = self.selected_agent_id()
        if not agent_id:
            QMessageBox.warning(self, self.tr("error"), self.tr("profile_required"))
            return
        if (
            QMessageBox.question(self, self.tr("confirm"), self.tr("delete_profile"))
            == QMessageBox.StandardButton.Yes
        ):
            self.service.delete_ai_agent(agent_id)
            self.refresh_agents()

    def edit_agent_dialog(self, existing=None) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("edit_profile") if existing else self.tr("add_profile"))
        form = QFormLayout(dialog)
        name = QLineEdit(existing["name"] if existing else "")
        provider = QComboBox()
        provider.addItems(["openai", "anthropic", "gemini"])
        provider.setCurrentText(existing["provider"] if existing else "openai")
        model = QLineEdit(existing["model"] if existing else "gpt-4.1-mini")
        token = QLineEdit()
        token.setEchoMode(QLineEdit.EchoMode.Password)
        if existing:
            token.setPlaceholderText(self.tr("api_key_optional"))
        form.addRow(self.tr("profile_name"), name)
        form.addRow(self.tr("provider"), provider)
        form.addRow(self.tr("model"), model)
        form.addRow(self.tr("api_key"), token)
        save = button(dialog, "save", self.tr("save"))
        save.clicked.connect(dialog.accept)
        form.addRow(save)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if (
            not name.text().strip()
            or not model.text().strip()
            or (existing is None and not token.text())
        ):
            QMessageBox.warning(self, self.tr("error"), self.tr("profile_key_required"))
            return
        try:
            if existing:
                self.service.update_ai_agent(
                    existing["id"],
                    name.text().strip(),
                    provider.currentText(),
                    model.text().strip(),
                    token.text(),
                )
            else:
                self.service.save_ai_agent(
                    name.text().strip(), provider.currentText(), model.text().strip(), token.text()
                )
        except ValueError as error:
            QMessageBox.warning(self, self.tr("error"), self.tr(str(error)))
            return
        self.refresh_agents()

    def open_folder(self) -> None:
        if self.service.image_directory():
            QDesktopServices.openUrl(self.service.image_directory().as_uri())

    def choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            self.tr("choose_folder"),
            self.settings_folder_path.text()
            if hasattr(self, "settings_folder_path")
            else str(self.service.image_directory() or ""),
        )
        if path and hasattr(self, "settings_folder_path"):
            self.settings_folder_path.setText(path)

    def bind_result_menu(self, field: QTextEdit) -> None:
        field.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        field.customContextMenuRequested.connect(lambda point: self.show_result_menu(field, point))

    def show_result_menu(self, field: QTextEdit, point) -> None:
        selected_text = field.textCursor().selectedText()
        if not selected_text:
            return
        menu = QMenu(field)
        copy_action = menu.addAction(self.tr("copy"))
        formatted = menu.addAction(self.tr("add_to_database"))
        raw = menu.addAction(self.tr("add_raw_to_database"))
        action = menu.exec(field.mapToGlobal(point))
        if action == copy_action:
            field.copy()
        elif action == formatted:
            self.open_equipment_dialog(
                "".join(character for character in selected_text if character.isalnum())
            )
        elif action == raw:
            self.open_equipment_dialog(selected_text)

    def open_equipment_dialog(self, text: str, existing=None, prefill=None) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("new_equipment"))
        form = QFormLayout(dialog)
        text_field = QTextEdit(text)
        contract = QLineEdit()
        operation = QComboBox()
        operation.addItem(self.tr("receipt"), "receipt")
        operation.addItem(self.tr("issue"), "issue")
        model = QComboBox()
        popular = self.service.popular_models()
        popular_ids = {item["id"] for item in popular}
        for item in [
            *popular,
            *(item for item in self.service.models() if item["id"] not in popular_ids),
        ]:
            model.addItem(item["name"], item["id"])
        date_time = QDateTimeEdit()
        date_time.setDateTime(QDateTime.currentDateTime())
        date_time.setCalendarPopup(True)
        if existing is not None or prefill is not None:
            source = existing if existing is not None else prefill
            contract.setText(source["contract_number"] or "")
            operation.setCurrentIndex(operation.findData(source["operation_type"]))
            model.setCurrentIndex(model.findData(source["device_model_id"]))
            date_time.setDateTime(
                QDateTime.fromString(source["registered_at"], Qt.DateFormat.ISODate)
            )
        code_field = QWidget(dialog)
        code_layout = QVBoxLayout(code_field)
        code_layout.setContentsMargins(0, 0, 0, 0)
        code_layout.addWidget(text_field)
        code_actions = QHBoxLayout()
        qr = button(code_field, "generate_qr", self.tr("generate_qr"))
        qr.clicked.connect(lambda: self.show_generated_code(text_field.toPlainText(), "qr"))
        barcode = button(code_field, "generate_barcode", self.tr("generate_barcode"))
        barcode.clicked.connect(
            lambda: self.show_generated_code(text_field.toPlainText(), "barcode")
        )
        code_actions.addWidget(qr)
        code_actions.addWidget(barcode)
        code_actions.addStretch()
        code_layout.addLayout(code_actions)
        form.addRow(self.tr("recognized_text"), code_field)
        form.addRow(self.tr("contract"), contract)
        form.addRow(self.tr("operation"), operation)
        form.addRow(self.tr("model"), model)
        form.addRow(self.tr("date_time"), date_time)
        if existing is not None:
            api_examples = button(dialog, "api_example", self.tr("api_request_examples"))
            api_examples.clicked.connect(lambda: self.show_device_api_examples(existing["id"]))
            copy_record = button(dialog, "copy_record", self.tr("copy_record"))
            copy_record.clicked.connect(lambda: self.copy_device_dialog(dialog, existing))
            form.addRow(api_examples)
            form.addRow(copy_record)
        save = button(dialog, "save", self.tr("save"))
        save.clicked.connect(
            lambda: self.save_context_device(
                dialog, text_field, contract, operation, model, date_time, existing, prefill
            )
        )
        form.addRow(save)
        dialog.exec()

    def copy_device_dialog(self, dialog: QDialog, device) -> None:
        dialog.reject()
        self.open_equipment_dialog(device["recognized_text"], prefill=device)

    def show_device_api_examples(self, device_id: int) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("api_request_examples"))
        layout = QVBoxLayout(dialog)
        examples = QTextEdit(dialog)
        examples.setReadOnly(True)
        examples.setPlainText(
            f"GET http://127.0.0.1:{self.service.api_port()}/api/v1/equipment/{device_id}\n"
            "Authorization: Bearer <your-key>\n\n"
            f"POST http://127.0.0.1:{self.service.api_port()}/api/v1/code/get\n"
            "Authorization: Bearer <your-key>\n"
            "Content-Type: application/json\n\n"
            f'{{\n  "record_id": {device_id},\n  "type": "qrcode"\n}}'
        )
        layout.addWidget(examples)
        close = button(dialog, "close", self.tr("close"))
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def show_generated_code(self, value: str, code_type: str) -> None:
        try:
            image_data = self.service.generate_code_png(value, code_type)
            filename = self.service.generated_code_filename(value, code_type)
        except ValueError as error:
            self.error(self.tr(str(error)))
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(image_data, "PNG"):
            self.error(self.tr("code_type_invalid"))
            return
        title = (
            self.tr("qrcode_title", code=value.strip())
            if code_type in {"qr", "qrcode"}
            else self.tr("barcode_title", code=value.strip())
        )
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        preview = QLabel(dialog)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setPixmap(pixmap)
        layout.addWidget(preview)
        actions = QHBoxLayout()
        save = button(dialog, "save", self.tr("save_png"))
        save.clicked.connect(lambda: self.save_generated_code(image_data, filename))
        close = button(dialog, "close", self.tr("close"))
        close.clicked.connect(dialog.accept)
        actions.addWidget(save)
        actions.addWidget(close)
        layout.addLayout(actions)
        dialog.exec()

    def save_generated_code(self, image_data: bytes, filename: str) -> None:
        destination, _ = QFileDialog.getSaveFileName(
            self, self.tr("save_png"), filename, "PNG (*.png)"
        )
        if not destination:
            return
        try:
            self.service.save_generated_code(Path(destination), image_data)
        except OSError as error:
            self.error(self.tr("code_save_failed", error=str(error)))

    def save_context_device(
        self,
        dialog: QDialog,
        text_field: QTextEdit,
        contract: QLineEdit,
        operation: QComboBox,
        model: QComboBox,
        date_time: QDateTimeEdit,
        existing=None,
        prefill=None,
    ) -> None:
        text = text_field.toPlainText().strip()
        if not text:
            self.error(self.tr("recognized_text_required"))
            text_field.setFocus()
            return
        if model.currentData() is None:
            self.error(self.tr("model_required"))
            model.setFocus()
            return
        data = {
            "recognized_text": text,
            "contract_number": contract.text(),
            "operation_type": operation.currentData(),
            "source_image_path": (existing or prefill)["source_image_path"]
            if (existing is not None or prefill is not None)
            else str(self.selected_image or ""),
            "device_model_id": model.currentData(),
            "registered_at": date_time.dateTime().toString(Qt.DateFormat.ISODate),
        }
        try:
            if existing is None:
                self.service.add_device(data)
            else:
                self.service.update_device(existing["id"], data)
        except ValueError as error:
            self.error(self.tr(str(error)))
            return
        self.refresh_equipment()
        self.refresh_statistics()
        dialog.accept()

    def refresh_equipment(self) -> None:
        date_from = (
            self.date_from.date().toString("yyyy-MM-dd")
            if self.date_from.date().year() > 2000
            else ""
        )
        date_to = (
            self.date_to.date().toString("yyyy-MM-dd") if self.date_to.date().year() > 2000 else ""
        )
        rows, self.equipment_pagination = self.service.devices(
            self.device_search.text().strip(),
            self.type_filter.currentData(),
            self.service_filter.currentData(),
            date_from,
            date_to,
            self.model_filter.currentData() or None,
            self.operation_filter.currentData(),
            getattr(self, "equipment_page", 1),
        )
        self.current_devices = rows
        self.devices_table.setRowCount(len(rows))
        pagination = self.equipment_pagination
        self.equipment_page_label.setText(
            str(self.equipment_page)
            if pagination is None
            else str(pagination["page"]) + "/" + str(pagination["pages"])
        )
        self.equipment_previous.setEnabled(pagination is not None and pagination["page"] > 1)
        self.equipment_next.setEnabled(
            pagination is not None and pagination["page"] < pagination["pages"]
        )
        self.equipment_page = 1 if pagination is None else pagination["page"]
        for row, device in enumerate(rows):
            self.fill(
                self.devices_table,
                row,
                [
                    self.service.display_time(device["registered_at"]),
                    device["contract_number"] or "",
                    self.tr(device["operation_type"]),
                    device["recognized_text"],
                    device["model_name"],
                    self.tr(device["device_type"]),
                    self.tr(device["service"]),
                    device["source_image_path"] or "",
                    "",
                ],
            )
            self.devices_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, device["id"])
            actions = QWidget()
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(4, 0, 4, 0)
            action_layout.setSpacing(6)
            edit = button(actions, "edit", self.tr("edit"))
            edit.clicked.connect(lambda _, index=row: self.edit_equipment(index))
            more = button(actions, "actions", self.tr("actions"))
            menu = QMenu(more)
            for title, icon_name, handler in (
                (
                    "open_source_image",
                    "folder",
                    lambda _checked=False, index=row: self.open_source_image(index),
                ),
                (
                    "generate_qr",
                    "generate_qr",
                    lambda _checked=False, index=row: self.show_generated_code(
                        self.current_devices[index]["recognized_text"], "qr"
                    ),
                ),
                (
                    "generate_barcode",
                    "generate_barcode",
                    lambda _checked=False, index=row: self.show_generated_code(
                        self.current_devices[index]["recognized_text"], "barcode"
                    ),
                ),
            ):
                action = menu.addAction(icon_for(more, icon_name), self.tr(title))
                action.triggered.connect(handler)
            menu.addSeparator()
            delete = menu.addAction(icon_for(more, "delete"), self.tr("delete"))
            delete.triggered.connect(lambda _checked=False, index=row: self.delete_equipment(index))
            more.setMenu(menu)
            action_layout.addWidget(edit)
            action_layout.addWidget(more)
            self.devices_table.setCellWidget(row, 8, actions)

    def change_equipment_page(self, offset: int) -> None:
        if self.equipment_pagination is None:
            return
        self.equipment_page = max(1, self.equipment_page + offset)
        self.refresh_equipment()

    def edit_equipment(self, row: int) -> None:
        self.open_equipment_dialog(
            self.current_devices[row]["recognized_text"], self.current_devices[row]
        )

    def open_source_image(self, row: int) -> None:
        path = Path(str(self.current_devices[row]["source_image_path"] or ""))
        if not path.is_file():
            QMessageBox.warning(self, self.tr("error"), self.tr("source_image_missing"))
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", f"/select,{path}"])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def delete_equipment(self, row: int) -> None:
        device = self.current_devices[row]
        if (
            QMessageBox.question(self, self.tr("confirm"), self.tr("delete_device"))
            == QMessageBox.StandardButton.Yes
        ):
            self.service.delete_device(device["id"])
            self.refresh_equipment()
            self.refresh_statistics()

    def export_equipment(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("export"), "equipment.csv", "CSV (*.csv)"
        )
        if path:
            date_from = (
                self.date_from.date().toString("yyyy-MM-dd")
                if self.date_from.date().year() > 2000
                else ""
            )
            date_to = (
                self.date_to.date().toString("yyyy-MM-dd")
                if self.date_to.date().year() > 2000
                else ""
            )
            rows = self.service.all_filtered_devices(
                self.device_search.text().strip(),
                self.type_filter.currentData(),
                self.service_filter.currentData(),
                date_from,
                date_to,
                self.model_filter.currentData() or None,
                self.operation_filter.currentData(),
            )
            self.service.export_devices(Path(path), rows)

    def refresh_models(self) -> None:
        rows = self.service.models()
        self.models_table.setSortingEnabled(False)
        self.models_table.setRowCount(len(rows))
        self.model_filter.clear()
        self.model_filter.addItem(self.tr("model"), "")
        for row, model in enumerate(rows):
            self.fill(
                self.models_table,
                row,
                [
                    model["name"],
                    self.tr(model["device_type"]),
                    self.tr(model["service"]),
                    model["usage_count"],
                    "",
                ],
            )
            self.models_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, model["id"])
            self.models_table.item(row, 3).setData(
                Qt.ItemDataRole.EditRole, int(model["usage_count"])
            )
            self.model_filter.addItem(model["name"], model["id"])
            actions = QWidget()
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(2, 0, 2, 0)
            edit = button(actions, "edit", self.tr("edit"))
            edit.clicked.connect(lambda _, index=row: self.edit_model(index))
            delete = button(actions, "delete", self.tr("delete"))
            delete.clicked.connect(lambda _, identifier=model["id"]: self.delete_model(identifier))
            action_layout.addWidget(edit)
            action_layout.addWidget(delete)
            self.models_table.setCellWidget(row, 4, actions)
        self.models_table.setSortingEnabled(True)
        self.models_table.sortItems(0, Qt.SortOrder.AscendingOrder)

    def import_models(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, self.tr("import_models"), "", "Excel (*.xlsx)")
        if not path:
            return
        try:
            result = self.service.import_models_xlsx(Path(path))
        except ValueError as error:
            self.error(self.tr(str(error)))
            return
        self.refresh_models()
        self.refresh_equipment()
        QMessageBox.information(
            self,
            self.tr("import_models"),
            self.tr(
                "model_import_summary",
                added=str(result["added"]),
                duplicates=str(result["duplicates"]),
                invalid=str(len(result["invalid_rows"])),
            ),
        )

    def add_model(self) -> None:
        self.open_model_dialog()

    def edit_model(self, row: int) -> None:
        item = self.models_table.item(row, 0)
        model = (
            next(
                (
                    entry
                    for entry in self.service.models()
                    if entry["id"] == item.data(Qt.ItemDataRole.UserRole)
                ),
                None,
            )
            if item
            else None
        )
        if model is not None:
            self.open_model_dialog(model)

    def open_model_dialog(self, existing=None) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("edit_model") if existing else self.tr("add_model"))
        form = QFormLayout(dialog)
        name = QLineEdit(existing["name"] if existing else "")
        device_type = QComboBox()
        device_type.addItem(self.tr("modem"), "modem")
        device_type.addItem(self.tr("tuner"), "tuner")
        device_type.setCurrentIndex(
            max(0, device_type.findData(existing["device_type"] if existing else "modem"))
        )
        service = QComboBox()
        service.addItem(self.tr("internet"), "internet")
        service.addItem(self.tr("television"), "television")
        service.setCurrentIndex(
            max(0, service.findData(existing["service"] if existing else "internet"))
        )
        form.addRow(self.tr("model_name"), name)
        form.addRow(self.tr("type"), device_type)
        form.addRow(self.tr("service"), service)
        save = button(dialog, "save", self.tr("save"))
        save.clicked.connect(dialog.accept)
        form.addRow(save)
        if dialog.exec() != QDialog.DialogCode.Accepted or not name.text().strip():
            return
        try:
            if existing:
                self.service.update_model(
                    existing["id"],
                    name.text().strip(),
                    device_type.currentData(),
                    service.currentData(),
                )
            else:
                self.service.add_model(
                    name.text().strip(), device_type.currentData(), service.currentData()
                )
        except ValueError as error:
            self.error(self.tr(str(error)))
            return
        self.refresh_models()
        self.refresh_equipment()
        self.refresh_statistics()

    def delete_model(self, model_id: int) -> None:
        if (
            QMessageBox.question(self, self.tr("confirm"), self.tr("delete_model"))
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self.service.delete_model(model_id)
            self.refresh_models()
            self.refresh_equipment()
            self.refresh_statistics()
        except ValueError as error:
            self.error(self.tr(str(error)))

    def refresh_statistics(self) -> None:
        summary = self.service.statistics_summary(self.statistics_mode.currentData())
        operations = summary["operations"]
        self.statistics_table.setRowCount(len(operations))
        categories = [self.period_label(period) for period in operations]
        receipt = [values["receipt"] for values in operations.values()]
        issue = [values["issue"] for values in operations.values()]
        for index, (period, values) in enumerate(operations.items()):
            self.fill(
                self.statistics_table,
                index,
                [
                    self.period_label(period),
                    values["receipt"],
                    values["issue"],
                    values["receipt"] + values["issue"],
                ],
            )
        self.operations_chart.setChart(
            self.make_bar_chart(
                self.tr("operation"),
                categories,
                [(self.tr("receipt"), receipt), (self.tr("issue"), issue)],
            )
        )
        services = summary["services"]
        self.services_chart.setChart(
            self.make_bar_chart(
                self.tr("service"),
                [self.tr(key) for key in services],
                [(self.tr("service"), list(services.values()))],
            )
        )
        models = dict(list(summary["models"].items())[:10])
        self.models_chart.setChart(
            self.make_bar_chart(
                self.tr("models"), list(models.keys()), [(self.tr("models"), list(models.values()))]
            )
        )

    def error(self, message: str) -> None:
        QMessageBox.warning(self, self.tr("error"), message)

    @staticmethod
    def table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    @staticmethod
    def fill(table: QTableWidget, row: int, values: list[object]) -> None:
        for column, value in enumerate(values):
            table.setItem(row, column, QTableWidgetItem(str(value)))
