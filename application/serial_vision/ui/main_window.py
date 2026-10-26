from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import (
    QSize,
    Qt,
    QThread,
    QTimer,
    QUrl,
)
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
)

from serial_vision.application_service import SerialVisionService
from serial_vision.i18n import t
from serial_vision.local_api import LocalApiServer
from serial_vision.settings import SettingsValues
from serial_vision.ui.buttons import apply_button_icons, button, icon_for, icon_size
from serial_vision.ui.help_dialog import HelpDialog
from serial_vision.ui.pages.api import ApiPage
from serial_vision.ui.pages.camera import CameraPage
from serial_vision.ui.pages.equipment import EquipmentPage
from serial_vision.ui.pages.models import ModelsPage
from serial_vision.ui.pages.recognition import RecognitionPage
from serial_vision.ui.pages.settings import SettingsPage
from serial_vision.ui.pages.statistics import StatisticsPage
from serial_vision.ui.pages.warehouses import WarehousesPage
from serial_vision.ui.theme import apply_theme
from serial_vision.ui.update_controller import UpdateController
from serial_vision.version import app_version
from serial_vision.warehouse.client import WarehouseClient


class MainWindow(QMainWindow):
    def __init__(self, service: SerialVisionService) -> None:
        super().__init__()
        self.service = service
        self.local_api = LocalApiServer(service)
        self.ui_locale = service.locale()
        self._closing = False
        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setInterval(50)
        self._shutdown_timer.timeout.connect(self.close)
        self.service.register_launch()
        self.startup_log_error = self.service.log_startup("Application startup started")
        self.setWindowTitle(self.translate("app_name"))
        self.setWindowIcon(self.icon())
        self.resize(1500, 920)
        self.tabs = QTabWidget()
        self.tabs.setIconSize(icon_size(service.icon_style()))
        self.setCentralWidget(self.tabs)
        self.recognition_page = RecognitionPage(service, self.ui_locale, self)
        self.equipment_page = EquipmentPage(
            service, self.ui_locale, lambda: self.recognition_page.selected_image, self
        )
        self.warehouse_client = WarehouseClient(
            service._database.path.parent / "warehouses.sqlite3",
            os.environ.get("SERIAL_VISION_WAREHOUSE_URL", ""),
            Path(os.environ["SERIAL_VISION_WAREHOUSE_CA_FILE"])
            if os.environ.get("SERIAL_VISION_WAREHOUSE_CA_FILE")
            else None,
        )
        self.warehouses_page = WarehousesPage(service, self.ui_locale, self.warehouse_client, self)
        self.models_page = ModelsPage(service, self.ui_locale, self)
        self.statistics_page = StatisticsPage(service, self.ui_locale, self)
        self.camera_page = CameraPage(service, self.ui_locale, self)
        self.api_page = ApiPage(service, self.ui_locale, self)
        self.settings_page = SettingsPage(service, self.ui_locale, self.local_api.configure, self)
        self.pages = (
            self.recognition_page,
            self.equipment_page,
            self.warehouses_page,
            self.models_page,
            self.statistics_page,
            self.camera_page,
            self.api_page,
            self.settings_page,
        )
        for page, name in zip(
            self.pages,
            (
                "recognition",
                "equipment",
                "warehouses",
                "models",
                "statistics",
                "scan",
                "api_integrations",
                "settings",
            ),
        ):
            self.tabs.addTab(page, self.tab_icon(name), self.translate(name))
            page.help_requested.connect(self.show_help)
            page.record_requested.connect(self.equipment_page.open_equipment_dialog)
            page.warehouse_requested.connect(self.open_warehouse_receipt)
        self.api_page.setEnabled(service.api_enabled())
        self.models_page.changed.connect(self.equipment_page.refresh_model_filter)
        self.models_page.changed.connect(self.equipment_page.refresh_equipment)
        self.models_page.changed.connect(self.statistics_page.refresh_statistics)
        self.equipment_page.changed.connect(self.models_page.refresh_models)
        self.equipment_page.changed.connect(self.statistics_page.refresh_statistics)
        self.settings_page.agents_changed.connect(self.recognition_page.refresh_agents)
        self.settings_page.saved.connect(self.settings_applied)
        self.settings_page.dirty_changed.connect(self.settings_dirty)
        self.warehouses_page.session_changed.connect(self.warehouse_permissions)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        if self.warehouse_client.requires_account_hint():
            self.warehouse_permissions(False, True)
        self.updates = UpdateController(service, self.ui_locale, self)
        self.updates.close_requested.connect(self.close)
        self.create_tray()
        self.create_menus()
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().addPermanentWidget(
            QLabel(
                f"{self.translate('developer')}  •  {self.translate('version', version=app_version())}"
            )
        )
        if service.api_enabled() and not self.warehouse_client.requires_account_hint():
            try:
                self.local_api.start()
            except OSError as error:
                QTimer.singleShot(
                    0,
                    lambda message=str(error): QMessageBox.warning(
                        self,
                        self.translate("error"),
                        self.translate("api_start_failed", error=message),
                    ),
                )
        if self.startup_log_error is None:
            service.log_startup("Main window is ready")
        else:
            QTimer.singleShot(0, self.retry_startup_log)
        if service.setup_required():
            self.show_first_run_setup()

    def settings_dirty(self, dirty: bool) -> None:
        index = self.tabs.indexOf(self.settings_page)
        self.tabs.setTabText(index, self.translate("settings") + (" *" if dirty else ""))

    def settings_applied(self, current: SettingsValues, previous: SettingsValues) -> None:
        self.warehouse_permissions(
            self.warehouses_page.user.get("role") == "admin", self.warehouses_page.initialized
        )
        if current.image_directory != previous.image_directory:
            self.recognition_page.image_page = 1
            self.recognition_page.clear_image_selection()
            self.recognition_page.refresh_images()
        if (current.theme, current.icon_style) != (previous.theme, previous.icon_style):
            app = QApplication.instance()
            if isinstance(app, QApplication):
                apply_button_icons(current.icon_style)
                self.tabs.setIconSize(icon_size(current.icon_style))
                for index, name in enumerate(
                    (
                        "recognition",
                        "equipment",
                        "warehouses",
                        "models",
                        "statistics",
                        "scan",
                        "api_integrations",
                        "settings",
                    )
                ):
                    self.tabs.setTabIcon(index, self.tab_icon(name))
                apply_theme(app, current.theme)

    def open_warehouse_receipt(self, serial: str) -> None:
        self.tabs.setCurrentWidget(self.warehouses_page)
        self.warehouses_page.prepare_receipt(serial)

    def warehouse_permissions(self, admin: bool, initialized: bool) -> None:
        initialized = initialized or self.warehouse_client.requires_account_hint()
        allowed = not self.warehouse_client.server_url and (not initialized or admin)
        self.api_page.setEnabled(allowed and self.service.api_enabled())
        self.settings_page.api_enabled.setEnabled(allowed)
        self.settings_page.api_port.setEnabled(allowed)
        if not allowed:
            self.local_api.stop()
        elif self.service.api_enabled() and self.local_api.server is None:
            try:
                self.local_api.start()
            except OSError as error:
                self.statusBar().showMessage(self.translate("api_start_failed", error=str(error)))

    def on_tab_changed(self, _index: int) -> None:
        if self.tabs.currentWidget() is self.warehouses_page:
            self.warehouses_page.activate()
        if self.tabs.currentWidget() is not self.camera_page:
            self.camera_page.stop_camera()

    def translate(self, key: str, **values: object) -> str:
        return t(self.ui_locale, key, **values)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._closing:
            self._closing = True
            self.updates.stop()
            self.camera_page.begin_shutdown()
            self.local_api.stop()
            self.recognition_page.begin_shutdown()
            self.statistics_page.begin_shutdown()
            self.warehouses_page.begin_shutdown()
            self.setEnabled(False)
            self.statusBar().showMessage(self.translate("shutdown_wait"))
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

    def retry_startup_log(self) -> None:
        error = self.service.log_startup(self.translate("startup_log_retry"))
        if error is not None:
            QMessageBox.warning(
                self,
                self.translate("error"),
                self.translate(
                    "startup_log_unavailable",
                    path=str(self.service.startup_log_path().parent),
                    error=str(error),
                ),
            )

    def tab_icon(self, name: str) -> QIcon:
        return icon_for(self, name)

    def create_tray(self) -> None:
        self.tray = QSystemTrayIcon(self.icon(), self)
        self.tray.setToolTip(self.translate("app_name"))
        menu = QMenu(self)
        show = QAction(self.translate("open"), self)
        show.triggered.connect(self.showNormal)
        exit_action = QAction(self.translate("exit"), self)
        exit_action.triggered.connect(self.close)
        menu.addActions([show, exit_action])
        self.tray.setContextMenu(menu)
        self.tray.show()

    def create_menus(self) -> None:
        file_menu = self.menuBar().addMenu(self.translate("menu_file"))
        choose = file_menu.addAction(self.translate("choose_folder"))
        choose.triggered.connect(self.settings_page.choose_folder)
        open_action = file_menu.addAction(self.translate("open_folder"))
        open_action.triggered.connect(self.recognition_page.open_folder)
        file_menu.addSeparator()
        exit_action = file_menu.addAction(self.translate("exit"))
        exit_action.triggered.connect(self.close)

        edit_menu = self.menuBar().addMenu(self.translate("menu_edit"))
        copy_action = edit_menu.addAction(self.translate("copy"))
        copy_action.triggered.connect(self.copy_active_text)
        rotate_action = edit_menu.addAction(self.translate("rotate"))
        rotate_action.triggered.connect(self.recognition_page.rotate)
        delete_action = edit_menu.addAction(self.translate("delete"))
        delete_action.triggered.connect(self.recognition_page.delete_image)

        view_menu = self.menuBar().addMenu(self.translate("menu_view"))
        for index, key in enumerate(
            (
                "recognition",
                "equipment",
                "warehouses",
                "models",
                "statistics",
                "scan",
                "api_integrations",
                "settings",
            )
        ):
            action = view_menu.addAction(self.translate(key))
            action.triggered.connect(
                lambda _checked=False, current=index: self.tabs.setCurrentIndex(current)
            )

        help_menu = self.menuBar().addMenu(self.translate("help"))
        help_action = help_menu.addAction(self.translate("help_contents"))
        help_action.triggered.connect(self.show_help)
        log_action = help_menu.addAction(self.translate("startup_log"))
        log_action.triggered.connect(self.open_startup_log)
        update_action = help_menu.addAction(self.translate("check_updates"))
        update_action.triggered.connect(self.updates.check_updates)
        about_action = help_menu.addAction(self.translate("about"))
        about_action.triggered.connect(self.show_about)

    def show_about(self) -> None:
        website_url = "https://webbooks.com.ua/portfolio-uk/?utm_source=webbooks&utm_medium=sidebar&utm_campaign=portfolio"
        dialog = QDialog(self)
        dialog.setWindowTitle(self.translate("about"))
        dialog.setWindowIcon(self.icon())
        dialog.setMinimumWidth(760)
        layout = QVBoxLayout(dialog)

        header = QHBoxLayout()
        logo = QLabel(dialog)
        logo.setPixmap(self.icon().pixmap(QSize(56, 56)))
        logo.setAccessibleName(self.translate("app_name"))
        header.addWidget(logo)
        description = QLabel(
            f"<b>{self.translate('app_name')}</b><br>{self.translate('about_description')}", dialog
        )
        description.setWordWrap(True)
        header.addWidget(description, 1)
        layout.addLayout(header)

        details = QFormLayout()
        version = app_version()
        details.addRow(self.translate("version_label"), QLabel(f"v{version}", dialog))
        details.addRow(self.translate("developer_label"), QLabel("homeandriy", dialog))
        website = QLabel(
            '<a href="https://webbooks.com.ua/portfolio-uk/?utm_source=webbooks&amp;utm_medium=sidebar&amp;utm_campaign=portfolio">webbooks.com.ua/portfolio-uk</a>',
            dialog,
        )
        website.setOpenExternalLinks(True)
        details.addRow(self.translate("website"), website)
        layout.addLayout(details)

        actions = QHBoxLayout()
        actions.addStretch()
        open_website = button(dialog, "open", self.translate("open_website"))
        open_website.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(website_url)))
        close = button(dialog, "close", self.translate("close"))
        close.clicked.connect(dialog.accept)
        actions.addWidget(open_website)
        actions.addWidget(close)
        layout.addLayout(actions)
        dialog.resize(760, 300)
        dialog.exec()

    def show_help(self, section_id: str | None = None) -> None:
        HelpDialog(self.ui_locale, section_id, self).exec()

    def copy_active_text(self) -> None:
        focused = QApplication.focusWidget()
        if isinstance(focused, QTextEdit) and focused.textCursor().hasSelection():
            focused.copy()
            return
        QMessageBox.information(self, self.translate("help"), self.translate("select_text_to_copy"))

    def open_startup_log(self) -> None:
        error = self.service.log_startup("User opened startup log")
        if error is not None:
            QMessageBox.warning(
                self,
                self.translate("error"),
                self.translate(
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
                self, self.translate("error"), self.translate("open_file_failed", error=str(error))
            )

    def show_first_run_setup(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        dialog.setWindowTitle(self.translate("first_run"))
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(self.translate("license_text")))
        accepted = QCheckBox(self.translate("license_acceptance"))
        layout.addWidget(accepted)
        path = QLineEdit()
        path.setReadOnly(True)
        choose = button(dialog, "folder", self.translate("choose_folder"))
        choose.clicked.connect(
            lambda: path.setText(
                QFileDialog.getExistingDirectory(dialog, self.translate("choose_folder"))
            )
        )
        layout.addWidget(path)
        layout.addWidget(choose)
        accept = button(dialog, "save", self.translate("accept_and_continue"))
        accept.clicked.connect(
            lambda: self.complete_first_run(dialog, path.text(), accepted.isChecked())
        )
        layout.addWidget(accept)
        dialog.exec()

    def complete_first_run(self, dialog: QDialog, path: str, accepted: bool) -> None:
        if not accepted:
            QMessageBox.warning(dialog, self.translate("error"), self.translate("license_required"))
            return
        try:
            self.service.complete_setup(Path(path))
        except ValueError:
            QMessageBox.warning(dialog, self.translate("error"), self.translate("folder_missing"))
            return
        self.recognition_page.refresh_images()
        dialog.accept()
